from app.services import moderation_service, referral_service, user_service


async def test_referral_self_invite_is_ignored(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=300)
    await session.commit()
    result = await referral_service.attribute_referral(session, new_user=alice, referral_code_used=alice.referral_code)
    assert result is None


async def test_referral_same_device_fingerprint_is_blocked(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=301, device_fingerprint="device-abc")
    bob, _ = await user_service.get_or_create_user(session, tg_id=302, device_fingerprint="device-abc")
    await session.commit()
    result = await referral_service.attribute_referral(session, new_user=bob, referral_code_used=alice.referral_code)
    assert result is None  # antifraud: same device => no payout


async def test_referral_valid_invite_is_attributed(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=303, device_fingerprint="device-A")
    bob, _ = await user_service.get_or_create_user(session, tg_id=304, device_fingerprint="device-B")
    await session.commit()
    result = await referral_service.attribute_referral(session, new_user=bob, referral_code_used=alice.referral_code)
    assert result is not None
    assert bob.referred_by_id == alice.id


def test_risk_keyword_detection_flags_payment_requests():
    assert moderation_service.detect_risk_score("привет, как дела?") == 0.0
    assert moderation_service.detect_risk_score("скинь предоплату на карту") > 0.0
    assert moderation_service.detect_risk_score("давай в биткоинах рассчитаемся") > 0.0


async def test_identical_message_spam_is_detected():
    user_id = 999
    text = "привет купи подписку"
    results = [await moderation_service.check_identical_message_spam(user_id, text) for _ in range(6)]
    assert results[-1] is True  # eventually flagged as spam after repeated identical text
