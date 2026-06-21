"""
API consumed by the Telegram Mini App (webapp/ static frontend).
Auth: every request must include header X-Telegram-Init-Data with the raw
Telegram.WebApp.initData string -- validated server-side (HMAC), so requests
can't be spoofed by a plain HTTP client without a real Telegram session.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.enums import Gender, Goal, SeekingGender
from app.core.telegram_auth import validate_init_data
from app.models.user import User
from app.services import (
    chat_service, community_service, contest_service, like_service,
    matching_service, metrics_service, profile_service, user_service,
)

router = APIRouter(prefix="/webapp", tags=["webapp"])


async def get_webapp_user(
    x_telegram_init_data: str = Header(default=""), session: AsyncSession = Depends(get_db)
) -> User:
    validated = validate_init_data(x_telegram_init_data)
    if validated is None or not validated.get("user"):
        raise HTTPException(status_code=401, detail="invalid_telegram_init_data")
    tg_user = validated["user"]
    user, _ = await user_service.get_or_create_user(
        session, tg_id=tg_user["id"], username=tg_user.get("username"), first_name=tg_user.get("first_name")
    )
    await session.commit()
    return user


# ---------- schemas ----------

class ProfileIn(BaseModel):
    city: str
    district: Optional[str] = None
    age: int
    gender: Gender
    seeking_gender: SeekingGender
    goal: Goal
    bio: Optional[str] = Field(default=None, max_length=280)
    interests: list[str]


# ---------- endpoints ----------

@router.get("/me")
async def whoami(user: User = Depends(get_webapp_user)):
    profile = user.profile
    return {
        "id": user.id, "tg_id": user.tg_id, "state": user.state.value,
        "has_profile": profile is not None,
        "profile": None if profile is None else {
            "city": profile.city, "district": profile.district, "age": profile.age,
            "gender": profile.gender.value, "seeking_gender": profile.seeking_gender.value,
            "goal": profile.goal.value, "bio": profile.bio,
            "interests": [ui.interest.code for ui in profile.interests],
        },
    }


@router.post("/profile")
async def upsert_profile(payload: ProfileIn, user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    try:
        profile = await profile_service.upsert_profile(
            session, user=user, city=payload.city, district=payload.district, age=payload.age,
            gender=payload.gender, seeking_gender=payload.seeking_gender, goal=payload.goal, bio=payload.bio,
        )
        await profile_service.set_interests(session, profile, payload.interests)
        from app.core.enums import UserState

        await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
        await session.commit()
    except profile_service.ProfileValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/candidates")
async def get_candidates(limit: int = 10, user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    candidates = await matching_service.find_candidates(session, user, limit=limit)
    return [
        {
            "user_id": p.user_id, "age": p.age, "city": p.city, "district": p.district,
            "goal": p.goal.value, "bio": p.bio,
            "interests": [ui.interest.name_ru for ui in p.interests],
            "photo_file_id": p.user.photos[0].telegram_file_id if p.user.photos else None,
        }
        for p in candidates
    ]


@router.post("/like/{target_user_id}")
async def like_candidate(target_user_id: int, user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    try:
        like, match = await like_service.record_like(session, user, target_user_id)
        await session.commit()
    except like_service.LikeLimitReached:
        raise HTTPException(status_code=429, detail="daily_like_limit_reached")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "matched": match is not None}


@router.post("/skip/{target_user_id}")
async def skip_candidate(target_user_id: int, user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    await like_service.record_skip(session, user, target_user_id)
    await session.commit()
    return {"ok": True}


@router.get("/chat")
async def get_my_chat(user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    from app.models.message import Message

    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        return {"active": False}
    res = await session.execute(select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at))
    messages = res.scalars().all()
    return {
        "active": True, "chat_id": chat.id, "expires_at": chat.expires_at.isoformat() if chat.expires_at else None,
        "extended_count": chat.extended_count,
        "messages": [{"sender_id": m.sender_id, "text": m.text, "created_at": m.created_at.isoformat()} for m in messages],
    }


class MessageIn(BaseModel):
    text: str = Field(max_length=4096)


@router.post("/chat/message")
async def send_chat_message(payload: MessageIn, user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    from app.models.message import Message as MessageModel
    from app.services import moderation_service

    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        raise HTTPException(status_code=400, detail="no_active_chat")
    if not await moderation_service.check_rate_limit(user.id):
        raise HTTPException(status_code=429, detail="rate_limited")

    db_message = MessageModel(chat_id=chat.id, sender_id=user.id, text=payload.text[:4096])
    session.add(db_message)
    await session.flush()
    await moderation_service.evaluate_message(session, db_message, chat.id)
    await chat_service.record_message_touch(session, chat)
    await session.commit()
    return {"ok": True}


@router.post("/chat/extend")
async def extend_my_chat(user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        raise HTTPException(status_code=400, detail="no_active_chat")
    extended = await chat_service.request_extend(session, chat, user.id)
    await session.commit()
    return {"extended": extended}


@router.get("/pulse")
async def webapp_pulse(user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    city = user.profile.city if user.profile else None
    return await metrics_service.pulse(session, city=city)


@router.get("/communities")
async def webapp_communities(session: AsyncSession = Depends(get_db)):
    communities = await community_service.list_communities(session)
    return [{"code": c.code, "name_ru": c.name_ru, "category": c.category.value} for c in communities]


@router.get("/events")
async def webapp_events(user: User = Depends(get_webapp_user), session: AsyncSession = Depends(get_db)):
    city = user.profile.city if user.profile else None
    contests = await contest_service.list_active_contests(session, city=city)
    return [{"id": c.id, "title": c.title, "type": c.type.value} for c in contests]
