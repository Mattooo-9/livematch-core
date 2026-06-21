from datetime import timedelta

import pytest

from app.core.enums import Gender, Goal, SeekingGender
from app.models.mixins import utcnow
from app.services import chat_service, like_service, profile_service, user_service


async def _make_matched_pair(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=100)
    bob, _ = await user_service.get_or_create_user(session, tg_id=101)
    for u, g, s in ((alice, Gender.FEMALE, SeekingGender.MALE), (bob, Gender.MALE, SeekingGender.FEMALE)):
        p = await profile_service.upsert_profile(session, u, city="Kyiv", age=25, gender=g, seeking_gender=s, goal=Goal.DATE)
        await profile_service.set_interests(session, p, ["MUSIC", "WALKS", "FOOD"])
    await session.commit()

    await like_service.record_like(session, alice, bob.id)
    _, match = await like_service.record_like(session, bob, alice.id)
    await session.commit()
    return alice, bob, match


async def test_mutual_like_creates_match_and_active_chat(session):
    alice, bob, match = await _make_matched_pair(session)
    assert match is not None
    chat = await chat_service.get_active_chat(session, alice.id)
    assert chat is not None
    assert chat.other_user(alice.id) == bob.id


async def test_duplicate_like_raises(session):
    alice, _ = await user_service.get_or_create_user(session, tg_id=200)
    bob, _ = await user_service.get_or_create_user(session, tg_id=201)
    p = await profile_service.upsert_profile(session, alice, city="Kyiv", age=25, gender=Gender.FEMALE, seeking_gender=SeekingGender.ANY, goal=Goal.DATE)
    await profile_service.set_interests(session, p, ["MUSIC", "WALKS", "FOOD"])
    await session.commit()
    await like_service.record_like(session, alice, bob.id)
    await session.commit()
    with pytest.raises(ValueError):
        await like_service.record_like(session, alice, bob.id)


async def test_chat_requires_both_sides_to_extend(session):
    alice, bob, match = await _make_matched_pair(session)
    chat = await chat_service.get_active_chat(session, alice.id)
    original_expiry = chat.expires_at

    extended_once = await chat_service.request_extend(session, chat, alice.id)
    assert extended_once is False
    assert chat.expires_at == original_expiry

    extended_twice = await chat_service.request_extend(session, chat, bob.id)
    assert extended_twice is True
    assert chat.expires_at > original_expiry
    assert chat.extended_count == 1


async def test_expired_chat_is_swept_and_buffer_promoted(session):
    alice, bob, match = await _make_matched_pair(session)
    chat = await chat_service.get_active_chat(session, alice.id)
    chat.expires_at = utcnow() - timedelta(hours=1)
    await session.commit()

    result = await chat_service.sweep_expired_and_inactive_chats(session)
    await session.commit()
    assert result["expired"] == 1

    closed_chat = await chat_service.get_active_chat(session, alice.id)
    assert closed_chat is None
