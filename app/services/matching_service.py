"""
Core matching algorithm.

Principles enforced here (per product spec):
- filter by city, district, goal, mutual gender preference, interests, activity
- interest overlap boosts ranking
- online/recent activity boosts ranking
- users who already received a lot of incoming attention recently are deprioritized
  (never fully hidden, just pushed down) -- this prevents a few profiles from
  hoarding all incoming attention
- users with no dialog for a long time are boosted back up
- beauty/photos are NEVER a ranking input -- there is no such signal in this query at all
- payments NEVER influence this ranking -- no "pay to boost" field exists anywhere here
"""
from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.interest import UserInterest
from app.models.like import Like
from app.models.match import Match
from app.models.metrics import EventLog
from app.models.mixins import utcnow
from app.models.profile import Profile
from app.models.user import User
from app.core.enums import MatchStatus


async def _excluded_user_ids(session: AsyncSession, user: User) -> set[int]:
    excluded = {user.id}

    res = await session.execute(select(Like.to_user_id).where(Like.from_user_id == user.id))
    excluded.update(res.scalars().all())

    res = await session.execute(
        select(EventLog.payload_json).where(EventLog.user_id == user.id, EventLog.event_type == "skip")
    )
    for raw in res.scalars().all():
        try:
            excluded.add(json.loads(raw)["to_user_id"])
        except Exception:
            continue

    res = await session.execute(
        select(Match.user_a_id, Match.user_b_id).where(
            and_(Match.status != MatchStatus.CLOSED, (Match.user_a_id == user.id) | (Match.user_b_id == user.id))
        )
    )
    for a, b in res.all():
        excluded.add(a)
        excluded.add(b)

    return excluded


def _mutual_gender_ok(me: Profile, other: Profile) -> bool:
    me_wants_other = me.seeking_gender.value == "ANY" or me.seeking_gender.value == other.gender.value
    other_wants_me = other.seeking_gender.value == "ANY" or other.seeking_gender.value == me.gender.value
    return me_wants_other and other_wants_me


async def find_candidates(session: AsyncSession, user: User, limit: int = 10) -> list[Profile]:
    me = user.profile
    if me is None:
        return []

    excluded = await _excluded_user_ids(session, user)

    stmt = (
        select(Profile)
        .options(
            selectinload(Profile.interests).selectinload(UserInterest.interest),
            selectinload(Profile.user),
        )
        .join(User, User.id == Profile.user_id)
        .where(
            Profile.user_id.notin_(excluded),
            User.is_banned.is_(False),
            User.is_admin.is_(False),
            Profile.city == me.city,
            Profile.goal == me.goal,
            Profile.is_invisible_pause.is_(False),
        )
        .limit(200)  # pull a wider pool, then score+rank in Python (pool sizes are small per city/goal)
    )
    res = await session.execute(stmt)
    pool = [p for p in res.scalars().all() if _mutual_gender_ok(me, p)]

    my_interest_ids = {ui.interest_id for ui in me.interests}
    now = utcnow()
    incoming_window = timedelta(hours=settings.INCOMING_LIMIT_WINDOW_HOURS)

    scored: list[tuple[float, Profile]] = []
    for candidate in pool:
        score = 0.0

        # 1. interest overlap -- the single biggest honest signal of compatibility
        their_interest_ids = {ui.interest_id for ui in candidate.interests}
        overlap = len(my_interest_ids & their_interest_ids)
        score += overlap * 10.0

        # 2. same district bonus (still same-city, just closer)
        if me.district and candidate.district and me.district == candidate.district:
            score += 5.0

        # 3. recent activity bonus (decays over 7 days)
        candidate_user_last_active = candidate.user.last_active_at if candidate.user else None
        if candidate_user_last_active:
            hours_since_active = (now - candidate_user_last_active).total_seconds() / 3600
            score += max(0.0, 10.0 - (hours_since_active / 16.8))  # ~0 after 7 days

        # 4. incoming-attention balancing: deprioritize people already saturated with likes
        window_active = (now - candidate.incoming_counter_reset_at) < incoming_window
        effective_incoming = candidate.incoming_counter if window_active else 0
        if effective_incoming > settings.INCOMING_LIKES_SOFT_LIMIT:
            score -= (effective_incoming - settings.INCOMING_LIKES_SOFT_LIMIT) * 1.5

        # 5. boost people who have been without any dialog for a long time
        if candidate.last_dialog_at is None:
            score += 6.0
        else:
            days_without_dialog = (now - candidate.last_dialog_at).total_seconds() / 86400
            score += min(8.0, days_without_dialog * 0.5)

        # NOTE: intentionally NO factor here reads Payment / is_paid / any "pay to boost" field.
        scored.append((score, candidate))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:limit]]
