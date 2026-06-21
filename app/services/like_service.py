"""Like / skip / match creation, daily like budget enforcement."""
from __future__ import annotations

import json
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import MatchStatus
from app.core.redis_client import safe_redis
from app.models.like import Like
from app.models.match import Match
from app.models.metrics import EventLog
from app.models.mixins import utcnow
from app.models.profile import Profile
from app.models.user import User
from app.services import chat_service, referral_service


class LikeLimitReached(Exception):
    pass


async def _daily_like_budget(session: AsyncSession, user: User) -> int:
    """Free budget + any referral/event bonuses granted today or unconsumed."""
    base = settings.FREE_LIKES_PER_DAY
    res = await session.execute(
        select(EventLog.payload_json).where(EventLog.user_id == user.id, EventLog.event_type == "referral_bonus_granted")
    )
    bonus = 0
    for raw in res.scalars().all():
        try:
            bonus += int(json.loads(raw).get("bonus_likes", 0))
        except Exception:
            continue
    return base + bonus


async def likes_used_today(user_id: int) -> int:
    redis = await safe_redis()
    key = f"likes_used:{user_id}:{date.today().isoformat()}"
    val = await redis.get(key)
    return int(val) if val else 0


async def _increment_likes_used(user_id: int) -> None:
    redis = await safe_redis()
    key = f"likes_used:{user_id}:{date.today().isoformat()}"
    await redis.incr(key)
    await redis.expire(key, 60 * 60 * 36)


async def record_skip(session: AsyncSession, user: User, target_user_id: int) -> None:
    session.add(EventLog(user_id=user.id, event_type="skip", payload_json=json.dumps({"to_user_id": target_user_id})))
    await session.flush()


async def record_like(session: AsyncSession, user: User, target_user_id: int) -> tuple[Like, Optional[Match]]:
    budget = await _daily_like_budget(session, user)
    used = await likes_used_today(user.id)
    if used >= budget:
        raise LikeLimitReached(f"daily_limit_reached:{used}/{budget}")

    existing = await session.execute(
        select(Like).where(Like.from_user_id == user.id, Like.to_user_id == target_user_id)
    )
    if existing.scalar_one_or_none():
        raise ValueError("already_liked")

    like = Like(from_user_id=user.id, to_user_id=target_user_id)
    session.add(like)
    await _increment_likes_used(user.id)

    # bump target's incoming counter (with window reset)
    res = await session.execute(select(Profile).where(Profile.user_id == target_user_id))
    target_profile = res.scalar_one_or_none()
    if target_profile:
        from datetime import timedelta

        window = timedelta(hours=settings.INCOMING_LIMIT_WINDOW_HOURS)
        if utcnow() - target_profile.incoming_counter_reset_at > window:
            target_profile.incoming_counter = 0
            target_profile.incoming_counter_reset_at = utcnow()
        target_profile.incoming_counter += 1

    await session.flush()

    # mutual like => match
    mutual = await session.execute(
        select(Like).where(Like.from_user_id == target_user_id, Like.to_user_id == user.id)
    )
    match: Optional[Match] = None
    if mutual.scalar_one_or_none():
        match = Match(user_a_id=user.id, user_b_id=target_user_id, status=MatchStatus.BUFFER)
        session.add(match)
        await session.flush()
        await chat_service.activate_or_buffer_chat_for_match(session, match)

        session.add(EventLog(user_id=user.id, event_type="match_created", payload_json=json.dumps({"match_id": match.id})))
        session.add(EventLog(user_id=target_user_id, event_type="match_created", payload_json=json.dumps({"match_id": match.id})))

        # first real activity -> try activating any pending referral for either side
        await referral_service.try_activate_referral(session, user)
        target_user = await session.get(User, target_user_id)
        if target_user:
            await referral_service.try_activate_referral(session, target_user)

    await session.flush()
    return like, match
