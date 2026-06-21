import pytest

from app.core.enums import Gender, Goal, SeekingGender
from app.services import matching_service, profile_service, user_service


async def _make_user(session, tg_id, city="Kyiv", goal=Goal.DATE, gender=Gender.FEMALE, seeking=SeekingGender.MALE, interests=None):
    user, _ = await user_service.get_or_create_user(session, tg_id=tg_id, username=f"u{tg_id}")
    profile = await profile_service.upsert_profile(
        session, user, city=city, age=25, gender=gender, seeking_gender=seeking, goal=goal, district="Center"
    )
    await profile_service.set_interests(session, profile, interests or ["MUSIC", "WALKS", "FOOD"])
    await session.commit()
    return user


async def test_profile_rejects_invalid_age(session):
    user, _ = await user_service.get_or_create_user(session, tg_id=1)
    with pytest.raises(profile_service.ProfileValidationError):
        await profile_service.upsert_profile(
            session, user, city="Kyiv", age=15, gender=Gender.MALE, seeking_gender=SeekingGender.ANY, goal=Goal.DATE
        )


async def test_profile_rejects_too_few_interests(session):
    user, _ = await user_service.get_or_create_user(session, tg_id=2)
    profile = await profile_service.upsert_profile(
        session, user, city="Kyiv", age=25, gender=Gender.MALE, seeking_gender=SeekingGender.ANY, goal=Goal.DATE
    )
    with pytest.raises(profile_service.ProfileValidationError):
        await profile_service.set_interests(session, profile, ["MUSIC"])


async def test_matching_finds_mutually_compatible_candidate(session):
    alice = await _make_user(session, tg_id=10, gender=Gender.FEMALE, seeking=SeekingGender.MALE)
    bob = await _make_user(session, tg_id=11, gender=Gender.MALE, seeking=SeekingGender.FEMALE)
    alice = await user_service.get_user_by_tg_id(session, 10)
    candidates = await matching_service.find_candidates(session, alice, limit=5)
    assert any(c.user_id == bob.id for c in candidates)


async def test_matching_excludes_incompatible_gender(session):
    alice = await _make_user(session, tg_id=20, gender=Gender.FEMALE, seeking=SeekingGender.MALE)
    eve = await _make_user(session, tg_id=21, gender=Gender.FEMALE, seeking=SeekingGender.FEMALE)
    alice = await user_service.get_user_by_tg_id(session, 20)
    candidates = await matching_service.find_candidates(session, alice, limit=5)
    assert all(c.user_id != eve.id for c in candidates)


async def test_matching_ranks_higher_interest_overlap_first(session):
    alice = await _make_user(session, tg_id=30, gender=Gender.FEMALE, seeking=SeekingGender.ANY, interests=["MUSIC", "WALKS", "FOOD"])
    low_overlap = await _make_user(session, tg_id=31, gender=Gender.MALE, seeking=SeekingGender.ANY, interests=["IT", "SPORT", "GAMES"])
    high_overlap = await _make_user(session, tg_id=32, gender=Gender.MALE, seeking=SeekingGender.ANY, interests=["MUSIC", "WALKS", "GAMES"])
    alice = await user_service.get_user_by_tg_id(session, 30)
    candidates = await matching_service.find_candidates(session, alice, limit=5)
    ids_in_order = [c.user_id for c in candidates]
    assert ids_in_order.index(high_overlap.id) < ids_in_order.index(low_overlap.id)
