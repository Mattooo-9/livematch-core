"""
Redis is used for everything ephemeral / high-frequency:
- online status (TTL keys)
- per-minute message rate limiting
- identical-message spam detection
- incoming-likes soft limit counters
- "new chats in last 10 minutes" pulse counter
- simple referral antifraud (device fingerprint dedup)

If Redis is unreachable, a fallback in-memory stub is used so the bot/api
do not crash in local dev without docker-compose. This is NOT for production.
"""
from __future__ import annotations

import time
from typing import Optional

import redis.asyncio as redis

from app.core.config import settings


class _InMemoryFallback:
    """Minimal subset of redis.asyncio API, used only if REDIS_URL is unreachable."""

    def __init__(self):
        self._store: dict[str, tuple[str, Optional[float]]] = {}

    async def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        value, expires_at = item
        if expires_at and expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value.encode() if isinstance(value, str) else value

    async def set(self, key: str, value, ex: Optional[int] = None):
        expires_at = time.time() + ex if ex else None
        self._store[key] = (value, expires_at)
        return True

    async def incr(self, key: str):
        item = self._store.get(key)
        current = int(item[0]) if item else 0
        current += 1
        expires_at = item[1] if item else None
        self._store[key] = (str(current), expires_at)
        return current

    async def expire(self, key: str, seconds: int):
        item = self._store.get(key)
        if item:
            self._store[key] = (item[0], time.time() + seconds)
        return True

    async def delete(self, *keys: str):
        for k in keys:
            self._store.pop(k, None)
        return True

    async def setex(self, key: str, seconds: int, value):
        return await self.set(key, value, ex=seconds)

    async def zadd(self, key: str, mapping: dict):
        return True

    async def zcount(self, key: str, lo, hi):
        return 0

    async def ping(self):
        return True

    async def scan_iter(self, match: str = "*"):
        import fnmatch
        for key in list(self._store.keys()):
            if fnmatch.fnmatch(key, match):
                yield key


_redis_client: Optional["redis.Redis"] = None
_fallback = _InMemoryFallback()


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def safe_redis():
    """Returns a working redis-like client, falling back to in-memory store on failure."""
    client = get_redis()
    try:
        await client.ping()
        return client
    except Exception:
        return _fallback
