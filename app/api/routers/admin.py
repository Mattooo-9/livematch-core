"""Admin REST API -- protected by X-Admin-Token header (see app/api/deps.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin_token
from app.core.enums import ModerationStatus, UserState
from app.models.moderation import ModerationQueueItem
from app.models.payment import Payment
from app.models.referral import Referral
from app.models.user import User
from app.services import ai_insight_service, metrics_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_token)])


@router.get("/metrics")
async def get_metrics(session: AsyncSession = Depends(get_db)):
    return await metrics_service.daily_aggregate_metrics(session)


@router.get("/pulse")
async def get_pulse(city: str | None = None, session: AsyncSession = Depends(get_db)):
    return await metrics_service.pulse(session, city=city)


@router.get("/users")
async def list_users(limit: int = 50, offset: int = 0, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    users = res.scalars().all()
    return [
        {"id": u.id, "tg_id": u.tg_id, "username": u.username, "state": u.state.value,
         "is_banned": u.is_banned, "risk_score": u.risk_score, "created_at": u.created_at.isoformat()}
        for u in users
    ]


@router.post("/users/{user_id}/limit")
async def limit_user(user_id: int, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    user.state = UserState.LIMITED
    await session.commit()
    return {"ok": True, "user_id": user_id, "state": user.state.value}


@router.post("/users/{user_id}/ban")
async def ban_user(user_id: int, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user_not_found")
    user.is_banned = True
    user.state = UserState.BANNED_BY_SYSTEM
    await session.commit()
    return {"ok": True, "user_id": user_id}


@router.get("/payments")
async def list_payments(limit: int = 50, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(Payment).order_by(Payment.created_at.desc()).limit(limit))
    payments = res.scalars().all()
    return [
        {"id": p.id, "user_id": p.user_id, "provider": p.provider.value, "feature": p.feature.value,
         "amount_minor": p.amount_minor, "currency": p.currency, "status": p.status.value,
         "created_at": p.created_at.isoformat()}
        for p in payments
    ]


@router.get("/referrals")
async def list_referrals(limit: int = 50, session: AsyncSession = Depends(get_db)):
    res = await session.execute(select(Referral).order_by(Referral.created_at.desc()).limit(limit))
    referrals = res.scalars().all()
    return [
        {"id": r.id, "referrer_id": r.referrer_id, "referred_id": r.referred_id, "status": r.status.value,
         "created_at": r.created_at.isoformat()}
        for r in referrals
    ]


@router.get("/moderation-queue")
async def moderation_queue(status: str = "OPEN", session: AsyncSession = Depends(get_db)):
    res = await session.execute(
        select(ModerationQueueItem).where(ModerationQueueItem.status == ModerationStatus(status)).order_by(
            ModerationQueueItem.created_at.desc()
        )
    )
    items = res.scalars().all()
    return [
        {"id": i.id, "signal_type": i.signal_type.value, "status": i.status.value,
         "target_user_id": i.target_user_id, "reporter_user_id": i.reporter_user_id,
         "reason": i.reason, "created_at": i.created_at.isoformat()}
        for i in items
    ]


@router.post("/moderation-queue/{item_id}/resolve")
async def resolve_moderation(item_id: int, note: str = "", session: AsyncSession = Depends(get_db)):
    item = await session.get(ModerationQueueItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item_not_found")
    item.status = ModerationStatus.RESOLVED
    item.resolution_note = note[:500]
    await session.commit()
    return {"ok": True}


@router.get("/ai-insights")
async def list_ai_insights(limit: int = 10, session: AsyncSession = Depends(get_db)):
    from app.models.metrics import AIInsight

    res = await session.execute(select(AIInsight).order_by(AIInsight.created_at.desc()).limit(limit))
    items = res.scalars().all()
    return [{"id": i.id, "report_date": i.report_date.isoformat(), "summary": i.summary} for i in items]


@router.post("/ai-insights/generate")
async def generate_ai_insight(session: AsyncSession = Depends(get_db)):
    insight = await ai_insight_service.generate_daily_insight(session)
    await session.commit()
    return {"id": insight.id, "report_date": insight.report_date.isoformat(), "summary": insight.summary}


@router.post("/tasks/restart")
async def restart_background_tasks():
    """
    Lightweight 'restart' hook for the in-process scheduler (see app/tasks/scheduler.py).
    In a multi-process deployment this should signal the worker process instead.
    """
    from app.tasks.scheduler import restart_scheduler

    await restart_scheduler()
    return {"ok": True}
