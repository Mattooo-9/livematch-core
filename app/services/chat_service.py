"""
Chat lifecycle: 1 active chat + 1 buffer match per user (FIFO queue if more
matches happen while both slots are busy -- see note below), 24h TTL with
mutual-extend, auto-close on expiry/inactivity, auto-promote buffer -> active.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ChatStatus
from app.models.chat import Chat
from app.models.match import Match
from app.models.mixins import utcnow
from app.models.profile import Profile


async def get_active_chat(session: AsyncSession, user_id: int) -> Optional[Chat]:
    res = await session.execute(
        select(Chat).where(
            Chat.status == ChatStatus.ACTIVE, or_(Chat.user_a_id == user_id, Chat.user_b_id == user_id)
        )
    )
    return res.scalar_one_or_none()


async def get_buffer_chats(session: AsyncSession, user_id: int) -> list[Chat]:
    res = await session.execute(
        select(Chat)
        .where(Chat.status == ChatStatus.BUFFER, or_(Chat.user_a_id == user_id, Chat.user_b_id == user_id))
        .order_by(Chat.created_at.asc())
    )
    return list(res.scalars().all())


async def activate_or_buffer_chat_for_match(session: AsyncSession, match: Match) -> Chat:
    a_has_active = await get_active_chat(session, match.user_a_id) is not None
    b_has_active = await get_active_chat(session, match.user_b_id) is not None

    if not a_has_active and not b_has_active:
        chat = Chat(
            match_id=match.id,
            user_a_id=match.user_a_id,
            user_b_id=match.user_b_id,
            status=ChatStatus.ACTIVE,
            started_at=utcnow(),
            expires_at=utcnow() + timedelta(hours=settings.ACTIVE_CHAT_TTL_HOURS),
        )
    else:
        # NOTE: simplification -- if either side already has an active chat,
        # the new chat is queued as BUFFER (FIFO per user when promoting).
        # This keeps "1 active + 1 buffer shown at a time" UX while still
        # recording every honest match instead of silently dropping it.
        chat = Chat(match_id=match.id, user_a_id=match.user_a_id, user_b_id=match.user_b_id, status=ChatStatus.BUFFER)

    session.add(chat)
    await session.flush()
    return chat


async def promote_next_buffer(session: AsyncSession, user_id: int) -> Optional[Chat]:
    """Called after a user's active chat closes -- pulls oldest buffer chat (for both sides) into ACTIVE."""
    buffers = await get_buffer_chats(session, user_id)
    for chat in buffers:
        other_id = chat.other_user(user_id)
        if await get_active_chat(session, other_id) is not None:
            continue  # the other person is still busy, try next buffer
        chat.status = ChatStatus.ACTIVE
        chat.started_at = utcnow()
        chat.expires_at = utcnow() + timedelta(hours=settings.ACTIVE_CHAT_TTL_HOURS)
        await session.flush()
        return chat
    return None


async def close_chat(session: AsyncSession, chat: Chat, reason: str) -> None:
    chat.status = ChatStatus.CLOSED
    chat.closed_reason = reason
    await session.flush()
    await promote_next_buffer(session, chat.user_a_id)
    await promote_next_buffer(session, chat.user_b_id)


async def request_extend(session: AsyncSession, chat: Chat, user_id: int) -> bool:
    """Returns True if the chat was actually extended (both sides agreed)."""
    if chat.status != ChatStatus.ACTIVE:
        return False
    if user_id == chat.user_a_id:
        chat.user_a_wants_extend = True
    elif user_id == chat.user_b_id:
        chat.user_b_wants_extend = True
    else:
        raise ValueError("user_not_in_chat")

    if chat.user_a_wants_extend and chat.user_b_wants_extend:
        if chat.extended_count >= settings.MAX_CHAT_EXTENSIONS:
            await session.flush()
            return False
        chat.expires_at = (chat.expires_at or utcnow()) + timedelta(hours=settings.ACTIVE_CHAT_TTL_HOURS)
        chat.extended_count += 1
        chat.user_a_wants_extend = False
        chat.user_b_wants_extend = False
        await session.flush()
        return True

    await session.flush()
    return False


async def record_message_touch(session: AsyncSession, chat: Chat) -> None:
    chat.last_message_at = utcnow()
    # touch "last_dialog_at" on both profiles -- used by matching algo to
    # boost people who've been without a dialog for a long time
    res = await session.execute(select(Profile).where(Profile.user_id.in_([chat.user_a_id, chat.user_b_id])))
    for profile in res.scalars().all():
        profile.last_dialog_at = utcnow()
    await session.flush()


async def sweep_expired_and_inactive_chats(session: AsyncSession) -> dict:
    """Run periodically by the scheduler (app/tasks)."""
    now = utcnow()
    closed = {"expired": 0, "inactive": 0}

    res = await session.execute(select(Chat).where(Chat.status == ChatStatus.ACTIVE, Chat.expires_at < now))
    for chat in res.scalars().all():
        await close_chat(session, chat, reason="expired_24h")
        closed["expired"] += 1

    inactivity_cutoff = now - timedelta(hours=settings.CHAT_INACTIVITY_AUTOCLOSE_HOURS)
    res = await session.execute(
        select(Chat).where(
            Chat.status == ChatStatus.ACTIVE,
            and_(Chat.last_message_at.is_(None) | (Chat.last_message_at < inactivity_cutoff)),
            Chat.started_at < inactivity_cutoff,
        )
    )
    for chat in res.scalars().all():
        await close_chat(session, chat, reason="inactivity")
        closed["inactive"] += 1

    return closed
