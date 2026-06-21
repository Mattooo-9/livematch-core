"""Interest communities -- help find people/events, not a noisy default chat."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Community, CommunityMember
from app.models.profile import Profile
from app.models.user import User


async def list_communities(session: AsyncSession) -> list[Community]:
    res = await session.execute(select(Community).order_by(Community.name_ru))
    return list(res.scalars().all())


async def join_community(session: AsyncSession, user_id: int, community_code: str) -> CommunityMember:
    res = await session.execute(select(Community).where(Community.code == community_code))
    community = res.scalar_one_or_none()
    if community is None:
        raise ValueError("unknown_community")

    res2 = await session.execute(
        select(CommunityMember).where(CommunityMember.community_id == community.id, CommunityMember.user_id == user_id)
    )
    existing = res2.scalar_one_or_none()
    if existing:
        return existing

    member = CommunityMember(community_id=community.id, user_id=user_id)
    session.add(member)
    await session.flush()
    return member


async def leave_community(session: AsyncSession, user_id: int, community_code: str) -> None:
    res = await session.execute(select(Community).where(Community.code == community_code))
    community = res.scalar_one_or_none()
    if community is None:
        return
    res2 = await session.execute(
        select(CommunityMember).where(CommunityMember.community_id == community.id, CommunityMember.user_id == user_id)
    )
    member = res2.scalar_one_or_none()
    if member:
        await session.delete(member)
        await session.flush()


async def my_communities(session: AsyncSession, user_id: int) -> list[Community]:
    res = await session.execute(
        select(Community).join(CommunityMember, CommunityMember.community_id == Community.id).where(
            CommunityMember.user_id == user_id
        )
    )
    return list(res.scalars().all())


async def community_members_in_city(
    session: AsyncSession, community_code: str, city: str, exclude_user_id: int, limit: int = 10
) -> list[User]:
    res = await session.execute(select(Community).where(Community.code == community_code))
    community = res.scalar_one_or_none()
    if community is None:
        return []
    res2 = await session.execute(
        select(User)
        .join(CommunityMember, CommunityMember.user_id == User.id)
        .join(Profile, Profile.user_id == User.id)
        .where(CommunityMember.community_id == community.id, Profile.city == city, User.id != exclude_user_id)
        .limit(limit)
    )
    return list(res2.scalars().all())
