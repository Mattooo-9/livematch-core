"""Profile create/update + interests (3-10 enforced here)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.enums import Gender, Goal, SeekingGender
from app.models.interest import Interest, UserInterest
from app.models.profile import Profile
from app.models.user import User

MIN_INTERESTS = 3
MAX_INTERESTS = 10


class ProfileValidationError(ValueError):
    pass


async def get_profile(session: AsyncSession, user_id: int) -> Optional[Profile]:
    res = await session.execute(
        select(Profile).options(selectinload(Profile.interests)).where(Profile.user_id == user_id)
    )
    return res.scalar_one_or_none()


async def upsert_profile(
    session: AsyncSession,
    user: User,
    city: str,
    age: int,
    gender: Gender,
    seeking_gender: SeekingGender,
    goal: Goal,
    district: str | None = None,
    geo_lat: float | None = None,
    geo_lon: float | None = None,
    radius_km: int | None = None,
    bio: str | None = None,
) -> Profile:
    if age < 18 or age > 99:
        raise ProfileValidationError("age_out_of_range")
    if not city or len(city) > 64:
        raise ProfileValidationError("invalid_city")

    profile = await get_profile(session, user.id)
    if profile is None:
        profile = Profile(
            user_id=user.id,
            city=city.strip()[:64],
            district=(district or "").strip()[:64] or None,
            geo_lat=geo_lat,
            geo_lon=geo_lon,
            age=age,
            gender=gender,
            seeking_gender=seeking_gender,
            goal=goal,
            radius_km=radius_km or settings.DEFAULT_SEARCH_RADIUS_KM,
            bio=(bio or "").strip()[:280] or None,
        )
        session.add(profile)
    else:
        profile.city = city.strip()[:64]
        profile.district = (district or "").strip()[:64] or None
        if geo_lat is not None:
            profile.geo_lat = geo_lat
        if geo_lon is not None:
            profile.geo_lon = geo_lon
        profile.age = age
        profile.gender = gender
        profile.seeking_gender = seeking_gender
        profile.goal = goal
        if radius_km:
            profile.radius_km = radius_km
        profile.bio = (bio or "").strip()[:280] or None

    await session.flush()
    return profile


async def set_interests(session: AsyncSession, profile: Profile, interest_codes: list[str]) -> Profile:
    unique_codes = list(dict.fromkeys(interest_codes))
    if not (MIN_INTERESTS <= len(unique_codes) <= MAX_INTERESTS):
        raise ProfileValidationError(f"interests_count_must_be_{MIN_INTERESTS}_{MAX_INTERESTS}")

    res = await session.execute(select(Interest).where(Interest.code.in_(unique_codes)))
    interests = res.scalars().all()
    if len(interests) != len(unique_codes):
        raise ProfileValidationError("unknown_interest_code")

    res2 = await session.execute(select(UserInterest).where(UserInterest.profile_id == profile.id))
    for existing in res2.scalars().all():
        await session.delete(existing)
    await session.flush()

    for interest in interests:
        session.add(UserInterest(profile_id=profile.id, interest_id=interest.id))
    await session.flush()
    return profile
