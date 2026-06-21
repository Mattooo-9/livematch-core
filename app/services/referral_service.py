"""
Referral program with light antifraud.

Rules implemented (per spec):
- inviter gets bonus action(s)
- invited gets a starter bonus
- only counted after invited user creates a profile AND has first activity (a like / message)
- antifraud: no payout for duplicate device fingerprints, same-tg-id self-referral,
  or referral code that doesn't exist
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ReferralStatus
from app.models.mixins import utcnow
from app.models.referral import Referral
from app.models.user import User


async def attribute_referral(session: AsyncSession, new_user: User, referral_code_used: str) -> Optional[Referral]:
    """Called right when a brand-new user starts the bot with a ?start=ref_<code> payload."""
    res = await session.execute(select(User).where(User.referral_code == referral_code_used))
    referrer = res.scalar_one_or_none()

    if not referrer:
        return None
    if referrer.id == new_user.id:
        return None  # can't refer yourself

    # antifraud: same device fingerprint as referrer => suspicious, skip silently
    if new_user.device_fingerprint and referrer.device_fingerprint:
        if new_user.device_fingerprint == referrer.device_fingerprint:
            return None

    new_user.referred_by_id = referrer.id
    referral = Referral(referrer_id=referrer.id, referred_id=new_user.id, status=ReferralStatus.PENDING)
    session.add(referral)
    await session.flush()
    return referral


async def try_activate_referral(session: AsyncSession, user: User) -> Optional[Referral]:
    """
    Call this after the user creates a profile AND performs first real activity
    (e.g. sends a like). Activates the referral and grants bonuses exactly once.
    """
    res = await session.execute(
        select(Referral).where(Referral.referred_id == user.id, Referral.status == ReferralStatus.PENDING)
    )
    referral = res.scalar_one_or_none()
    if not referral:
        return None

    if user.profile is None:
        return None

    referral.status = ReferralStatus.ACTIVATED
    referral.activated_at = utcnow()

    # Bonuses are granted as extra daily likes via EventLog-driven counters,
    # consumed by the matching/like service when computing the daily like budget.
    from app.models.metrics import EventLog
    import json

    session.add(EventLog(
        user_id=referral.referrer_id,
        event_type="referral_bonus_granted",
        payload_json=json.dumps({"bonus_likes": settings.REFERRAL_INVITER_BONUS_LIKES, "role": "referrer"}),
    ))
    session.add(EventLog(
        user_id=referral.referred_id,
        event_type="referral_bonus_granted",
        payload_json=json.dumps({"bonus_likes": settings.REFERRAL_INVITED_BONUS_LIKES, "role": "referred"}),
    ))
    await session.flush()
    return referral
