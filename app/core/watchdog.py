"""
Built-in background watchdog.
Monitors: memory usage, bot polling health, scheduler health.
Auto-restarts the bot process on critical failures.
Sends alert to admin Telegram on restart.
"""
from __future__ import annotations
import asyncio, gc, logging, os, sys, time
from typing import Optional

import psutil

log = logging.getLogger("livematch.watchdog")

# Thresholds
MAX_MEMORY_MB      = int(os.environ.get("WATCHDOG_MAX_MEM_MB", "400"))
MAX_RESTART_COUNT  = int(os.environ.get("WATCHDOG_MAX_RESTARTS", "10"))
CHECK_INTERVAL_SEC = int(os.environ.get("WATCHDOG_INTERVAL_SEC", "60"))

_restart_count = 0
_last_check_ok = time.time()
_watchdog_task: Optional[asyncio.Task] = None


def _memory_mb() -> float:
    try:
        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


async def _alert_admin(msg: str) -> None:
    from app.core.config import settings
    if not settings.BOT_TOKEN or not settings.admin_ids:
        return
    try:
        import httpx
        for admin_id in settings.admin_ids:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_id, "text": f"⚠️ LiveMatch Watchdog:\n{msg}"},
                )
    except Exception as e:
        log.error(f"Alert failed: {e}")


async def _watchdog_loop(bot_restart_fn):
    global _restart_count, _last_check_ok

    log.info(f"Watchdog started (max_mem={MAX_MEMORY_MB}MB, interval={CHECK_INTERVAL_SEC}s)")

    while True:
        await asyncio.sleep(CHECK_INTERVAL_SEC)
        try:
            mem = _memory_mb()
            log.debug(f"Watchdog check: mem={mem:.1f}MB restarts={_restart_count}")

            if mem > MAX_MEMORY_MB:
                log.warning(f"Memory limit exceeded: {mem:.1f}MB > {MAX_MEMORY_MB}MB — triggering GC")
                gc.collect()
                await asyncio.sleep(5)
                mem_after = _memory_mb()

                if mem_after > MAX_MEMORY_MB * 0.9:
                    if _restart_count >= MAX_RESTART_COUNT:
                        log.critical("Max restarts reached — hard exit")
                        await _alert_admin(f"💀 Max restarts ({MAX_RESTART_COUNT}) reached. Manual intervention needed.")
                        sys.exit(1)

                    _restart_count += 1
                    log.error(f"Restarting bot (attempt {_restart_count}): mem={mem_after:.1f}MB")
                    await _alert_admin(
                        f"🔄 Auto-restart #{_restart_count}\n"
                        f"Memory: {mem_after:.1f}MB/{MAX_MEMORY_MB}MB\n"
                        f"Uptime: {int(time.time() - _last_check_ok)}s since last ok"
                    )
                    await bot_restart_fn()

            _last_check_ok = time.time()

        except asyncio.CancelledError:
            log.info("Watchdog stopping")
            break
        except Exception as e:
            log.error(f"Watchdog error: {e}")


async def start_watchdog(bot_restart_fn) -> asyncio.Task:
    global _watchdog_task
    _watchdog_task = asyncio.create_task(_watchdog_loop(bot_restart_fn))
    return _watchdog_task


async def stop_watchdog():
    global _watchdog_task
    if _watchdog_task:
        _watchdog_task.cancel()
        try:
            await _watchdog_task
        except asyncio.CancelledError:
            pass
