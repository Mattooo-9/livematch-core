"""
PaymentService: provider-agnostic orchestration.
- creates a pending Payment row
- on success (Stars successful_payment OR fiat webhook), marks SUCCESS and
  activates the purchased feature
- exposes purchase history per user
"""
from __future__ import annotations


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PaidFeature, PaymentProviderName, PaymentStatus
from app.models.mixins import utcnow
from app.models.payment import Payment
from app.models.profile import Profile
from app.payments.catalog import FEATURE_CATALOG
from app.payments.fondy_provider import FondyProvider
from app.payments.liqpay_provider import LiqPayProvider
from app.payments.stripe_provider import StripeProvider
from app.payments.telegram_stars import TelegramStarsProvider
from app.payments.wayforpay_provider import WayForPayProvider

PROVIDERS = {
    PaymentProviderName.TELEGRAM_STARS: TelegramStarsProvider(),
    PaymentProviderName.STRIPE: StripeProvider(),
    PaymentProviderName.LIQPAY: LiqPayProvider(),
    PaymentProviderName.FONDY: FondyProvider(),
    PaymentProviderName.WAYFORPAY: WayForPayProvider(),
}


def get_provider(name: PaymentProviderName):
    return PROVIDERS[name]


async def create_pending_payment(
    session: AsyncSession, user_id: int, feature: PaidFeature, provider: PaymentProviderName
) -> Payment:
    pricing = FEATURE_CATALOG[feature]
    amount_minor = pricing["stars"] if provider == PaymentProviderName.TELEGRAM_STARS else pricing["fiat_cents"]
    currency = "XTR" if provider == PaymentProviderName.TELEGRAM_STARS else "USD"

    payment = Payment(
        user_id=user_id,
        provider=provider,
        feature=feature,
        amount_minor=amount_minor,
        currency=currency,
        status=PaymentStatus.PENDING,
        payload=f"{feature.value}:{user_id}:{int(utcnow().timestamp())}",
    )
    session.add(payment)
    await session.flush()
    return payment


async def mark_success_and_activate(session: AsyncSession, payment: Payment, external_id: str | None = None) -> Payment:
    payment.status = PaymentStatus.SUCCESS
    if external_id:
        payment.external_id = external_id
    await activate_feature(session, payment)
    await session.flush()
    return payment


async def activate_feature(session: AsyncSession, payment: Payment) -> None:
    """Applies the immediate, honest effect of a purchase. No ranking/beauty boosts here."""
    res = await session.execute(select(Profile).where(Profile.user_id == payment.user_id))
    profile = res.scalar_one_or_none()
    if profile is None:
        return

    if payment.feature == PaidFeature.EXTENDED_RADIUS:
        profile.radius_km = min(100, profile.radius_km + 25)
    elif payment.feature == PaidFeature.INVISIBLE_PAUSE:
        profile.is_invisible_pause = True
    elif payment.feature == PaidFeature.EXTRA_LIKES:
        from app.models.metrics import EventLog
        import json

        session.add(EventLog(
            user_id=payment.user_id,
            event_type="referral_bonus_granted",  # reuses the same daily-budget bonus mechanism
            payload_json=json.dumps({"bonus_likes": 10, "role": "paid_extra_likes"}),
        ))
    # EXTEND_CHAT / EARLY_ACCESS / CREATE_COMMUNITY_EVENT / PAID_CONTEST_ENTRY / EXTENDED_STATS / DONATION
    # are applied contextually by the bot handler that triggered the purchase
    # (e.g. EXTEND_CHAT calls chat_service.request_extend twice / force-extends).
    await session.flush()


async def purchase_history(session: AsyncSession, user_id: int) -> list[Payment]:
    res = await session.execute(
        select(Payment).where(Payment.user_id == user_id).order_by(Payment.created_at.desc())
    )
    return list(res.scalars().all())
