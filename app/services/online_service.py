"""Lightweight presence tracking via Redis TTL keys -- powers the live 'pulse'."""
from __future__ import annotations

from app.core.redis_client import safe_redis

ONLINE_TTL_SECONDS = 180


async def mark_online(user_id: int, city: str | None = None) -> None:
    redis = await safe_redis()
    await redis.setex(f"online:{user_id}", ONLINE_TTL_SECONDS, "1")
    if city:
        await redis.setex(f"online_city:{user_id}", ONLINE_TTL_SECONDS, city)


async def is_online(user_id: int) -> bool:
    redis = await safe_redis()
    return (await redis.get(f"online:{user_id}")) is not None
