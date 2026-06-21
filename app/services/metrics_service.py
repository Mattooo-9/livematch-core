"""
Pulse (live, no fake activity) + daily aggregate metrics that feed AIInsight.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import safe_redis
from app.models.chat import Chat
from app.models.like import Like
from app.models.match import Match
from app.models.mixins import utcnow
from app.models.payment import Payment
from app.models.profile import Profile
from app.models.referral import Referral
from app.models.user import User
from app.core.enums import ChatStatus, PaymentStatus, ReferralStatus


async def pulse(session: AsyncSession, city: str | None = None) -> dict:
    """Real, queryable, non-fake 'is this place alive' numbers."""
    now = utcnow()
    ten_min_ago = now - timedelta(minutes=10)

    redis = await safe_redis()
    # online now: scan isn't ideal at scale, but fine for MVP/early traffic
    online_now = 0
    try:
        async for _ in redis.scan_iter(match="online:*"):
            online_now += 1
    except Exception:
        online_now = 0

    new_chats_stmt = select(func.count(Chat.id)).where(Chat.created_at >= ten_min_ago)
    new_chats_10min = (await session.execute(new_chats_stmt)).scalar_one()

    active_users_stmt = select(func.count(User.id)).where(User.last_active_at >= now - timedelta(hours=24))
    if city:
        active_users_stmt = active_users_stmt.join(Profile, Profile.user_id == User.id).where(Profile.city == city)
    active_users_24h = (await session.execute(active_users_stmt)).scalar_one()

    return {
        "online_now": online_now,
        "new_chats_last_10_min": new_chats_10min,
        "active_users_24h": active_users_24h,
        "city": city,
        "generated_at": now.isoformat(),
    }


async def daily_aggregate_metrics(session: AsyncSession) -> dict:
    now = utcnow()
    day_ago = now - timedelta(hours=24)

    new_users_24h = (await session.execute(select(func.count(User.id)).where(User.created_at >= day_ago))).scalar_one()
    active_users_24h = (
        await session.execute(select(func.count(User.id)).where(User.last_active_at >= day_ago))
    ).scalar_one()
    likes_24h = (await session.execute(select(func.count(Like.id)).where(Like.created_at >= day_ago))).scalar_one()
    matches_24h = (await session.execute(select(func.count(Match.id)).where(Match.created_at >= day_ago))).scalar_one()
    chats_24h = (await session.execute(select(func.count(Chat.id)).where(Chat.created_at >= day_ago))).scalar_one()

    total_chats = (await session.execute(select(func.count(Chat.id)))).scalar_one()
    empty_chats = (
        await session.execute(select(func.count(Chat.id)).where(Chat.last_message_at.is_(None), Chat.status == ChatStatus.CLOSED))
    ).scalar_one()
    empty_chat_pct = (empty_chats / total_chats * 100) if total_chats else 0.0

    extended_chats = (await session.execute(select(func.count(Chat.id)).where(Chat.extended_count > 0))).scalar_one()
    extension_pct = (extended_chats / total_chats * 100) if total_chats else 0.0

    paid_actions_24h = (
        await session.execute(
            select(func.count(Payment.id)).where(Payment.created_at >= day_ago, Payment.status == PaymentStatus.SUCCESS)
        )
    ).scalar_one()

    referrals_activated_24h = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.activated_at >= day_ago, Referral.status == ReferralStatus.ACTIVATED)
        )
    ).scalar_one()

    avg_risk_score = (await session.execute(select(func.avg(User.risk_score)))).scalar() or 0.0
    avg_spam_score = (await session.execute(select(func.avg(User.spam_score)))).scalar() or 0.0

    # retention D1/D7 -- simplified cohort check: users created N days ago who were active in last 24h
    def _retention_query(days: int):
        cohort_start = now - timedelta(days=days + 1)
        cohort_end = now - timedelta(days=days)
        return cohort_start, cohort_end

    d1_start, d1_end = _retention_query(1)
    d1_cohort = (
        await session.execute(select(func.count(User.id)).where(User.created_at >= d1_start, User.created_at < d1_end))
    ).scalar_one()
    d1_retained = (
        await session.execute(
            select(func.count(User.id)).where(
                User.created_at >= d1_start, User.created_at < d1_end, User.last_active_at >= day_ago
            )
        )
    ).scalar_one()
    retention_d1 = (d1_retained / d1_cohort * 100) if d1_cohort else None

    d7_start, d7_end = _retention_query(7)
    d7_cohort = (
        await session.execute(select(func.count(User.id)).where(User.created_at >= d7_start, User.created_at < d7_end))
    ).scalar_one()
    d7_retained = (
        await session.execute(
            select(func.count(User.id)).where(
                User.created_at >= d7_start, User.created_at < d7_end, User.last_active_at >= day_ago
            )
        )
    ).scalar_one()
    retention_d7 = (d7_retained / d7_cohort * 100) if d7_cohort else None

    return {
        "generated_at": now.isoformat(),
        "new_users_24h": new_users_24h,
        "active_users_24h": active_users_24h,
        "likes_24h": likes_24h,
        "matches_24h": matches_24h,
        "chats_24h": chats_24h,
        "empty_chat_pct": round(empty_chat_pct, 1),
        "chat_extension_pct": round(extension_pct, 1),
        "paid_actions_24h": paid_actions_24h,
        "referrals_activated_24h": referrals_activated_24h,
        "avg_risk_score": round(float(avg_risk_score), 3),
        "avg_spam_score": round(float(avg_spam_score), 3),
        "retention_d1_pct": round(retention_d1, 1) if retention_d1 is not None else None,
        "retention_d7_pct": round(retention_d7, 1) if retention_d7 is not None else None,
    }
