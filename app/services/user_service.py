"""User lifecycle: get-or-create, state transitions, activity tracking."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserState
from app.models.mixins import utcnow
from app.models.user import User
from app.services.referral_service import attribute_referral


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    return res.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    tg_id: int,
    username: str | None = None,
    first_name: str | None = None,
    referral_code_used: str | None = None,
    device_fingerprint: str | None = None,
    is_admin: bool = False,
) -> tuple[User, bool]:
    """Returns (user, created)."""
    user = await get_user_by_tg_id(session, tg_id)
    if user:
        user.last_active_at = utcnow()
        if username:
            user.username = username
        return user, False

    user = User(
        tg_id=tg_id,
        username=username,
        first_name=first_name,
        state=UserState.NEW,
        device_fingerprint=device_fingerprint,
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()  # get user.id

    if referral_code_used:
        await attribute_referral(session, new_user=user, referral_code_used=referral_code_used)

    return user, True


async def set_state(session: AsyncSession, user: User, new_state: UserState) -> None:
    user.state = new_state
    user.last_active_at = utcnow()


async def touch_activity(session: AsyncSession, user: User) -> None:
    user.last_active_at = utcnow()
