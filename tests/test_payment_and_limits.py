import pytest

from app.core.enums import Gender, Goal, PaidFeature, PaymentProviderName, SeekingGender
from app.services import like_service, payment_service, profile_service, user_service


async def test_payment_success_activates_extended_radius(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=400)
    profile = await profile_service.upsert_profile(
        session, alice, city="Kyiv", age=25, gender=Gender.FEMALE, seeking_gender=SeekingGender.ANY, goal=Goal.DATE
    )
    await profile_service.set_interests(session, profile, ["MUSIC", "WALKS", "FOOD"])
    await session.commit()

    original_radius = profile.radius_km
    payment = await payment_service.create_pending_payment(session, alice.id, PaidFeature.EXTENDED_RADIUS, PaymentProviderName.TELEGRAM_STARS)
    assert payment.status.value == "PENDING"

    await payment_service.mark_success_and_activate(session, payment, external_id="charge_1")
    await session.commit()

    assert payment.status.value == "SUCCESS"
    assert profile.radius_km == min(100, original_radius + 25)


async def test_payment_never_influences_matching_score():
    """Static guard: matching_service must never import/read Payment data for ranking."""
    import inspect

    from app.services import matching_service

    source = inspect.getsource(matching_service)
    assert "import" not in source or "Payment" not in "\n".join(
        line for line in source.splitlines() if "import" in line
    )
    assert "models.payment" not in source
    assert ".is_paid" not in source
    assert "paid_boost" not in source


async def test_daily_like_limit_is_enforced(session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "FREE_LIKES_PER_DAY", 2)

    alice, _ = await user_service.get_or_create_user(session, tg_id=500)
    p = await profile_service.upsert_profile(session, alice, city="Kyiv", age=25, gender=Gender.FEMALE, seeking_gender=SeekingGender.ANY, goal=Goal.DATE)
    await profile_service.set_interests(session, p, ["MUSIC", "WALKS", "FOOD"])

    targets = []
    for i in range(3):
        u, _ = await user_service.get_or_create_user(session, tg_id=501 + i)
        targets.append(u)
    await session.commit()

    await like_service.record_like(session, alice, targets[0].id)
    await like_service.record_like(session, alice, targets[1].id)
    await session.commit()

    with pytest.raises(like_service.LikeLimitReached):
        await like_service.record_like(session, alice, targets[2].id)
