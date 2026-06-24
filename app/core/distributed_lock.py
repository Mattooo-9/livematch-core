"""
Redis-based distributed lock for Active-Passive bot cluster.
Only ONE instance processes updates at a time — even if both Koyeb and Vercel are running.
Uses SET NX PX (atomic) — safe against race conditions and network partitions.
"""
from __future__ import annotations
import asyncio, os, time, uuid
from typing import Optional
from app.core.redis_client import safe_redis

LOCK_KEY       = "livematch:bot:leader_lock"
LOCK_TTL_MS    = 30_000   # 30 sec — renewed every 10 sec by active leader
RENEW_INTERVAL = 10       # seconds
NODE_ID        = os.environ.get("KOYEB_INSTANCE_ID") or os.environ.get("VERCEL_REGION") or str(uuid.uuid4())[:8]

_is_leader   = False
_renew_task: Optional[asyncio.Task] = None


async def try_acquire_lock() -> bool:
    """Try to become leader. Returns True if this node is now the leader."""
    redis = await safe_redis()
    result = await redis.set(LOCK_KEY, NODE_ID, nx=True, px=LOCK_TTL_MS)
    return result is not None


async def renew_lock() -> bool:
    """Renew lock if we still own it. Returns False if we lost leadership."""
    redis = await safe_redis()
    val = await redis.get(LOCK_KEY)
    if val != NODE_ID:
        return False
    await redis.pexpire(LOCK_KEY, LOCK_TTL_MS)
    return True


async def release_lock() -> None:
    redis = await safe_redis()
    val = await redis.get(LOCK_KEY)
    if val == NODE_ID:
        await redis.delete(LOCK_KEY)


async def _renew_loop():
    global _is_leader
    while _is_leader:
        await asyncio.sleep(RENEW_INTERVAL)
        if not await renew_lock():
            _is_leader = False
            import logging
            logging.getLogger("livematch.lock").warning(
                f"[{NODE_ID}] Lost leadership — entering standby"
            )


async def start_leader_election() -> bool:
    """
    Called on bot startup. 
    - If we acquire the lock: start polling, begin renewing
    - If not: enter standby (passive mode — no polling)
    """
    global _is_leader, _renew_task
    import logging
    log = logging.getLogger("livematch.lock")

    for attempt in range(6):  # retry for 30 sec on startup
        if await try_acquire_lock():
            _is_leader = True
            _renew_task = asyncio.create_task(_renew_loop())
            log.info(f"[{NODE_ID}] Acquired leadership — ACTIVE mode")
            return True
        log.info(f"[{NODE_ID}] Lock taken, retrying in 5s ({attempt+1}/6)...")
        await asyncio.sleep(5)

    log.info(f"[{NODE_ID}] Entering PASSIVE standby mode")
    return False


async def stop_leader_election():
    global _is_leader, _renew_task
    _is_leader = False
    if _renew_task:
        _renew_task.cancel()
    await release_lock()


def is_leader() -> bool:
    return _is_leader


NODE_ID_VALUE = NODE_ID
