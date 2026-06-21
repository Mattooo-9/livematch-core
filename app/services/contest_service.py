"""Weekly mini-events. Voluntary, playful, never a public beauty ranking."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contest import Contest, ContestEntry
from app.models.mixins import utcnow


async def list_active_contests(session: AsyncSession, city: str | None = None) -> list[Contest]:
    now = utcnow()
    stmt = select(Contest).where(Contest.is_active.is_(True), Contest.starts_at <= now, Contest.ends_at >= now)
    if city:
        stmt = stmt.where((Contest.city == city) | (Contest.city.is_(None)))
    res = await session.execute(stmt.order_by(Contest.ends_at))
    return list(res.scalars().all())


async def join_contest(session: AsyncSession, contest_id: int, user_id: int, payload: str | None = None) -> ContestEntry:
    entry = ContestEntry(contest_id=contest_id, user_id=user_id, payload=payload)
    session.add(entry)
    await session.flush()
    return entry
