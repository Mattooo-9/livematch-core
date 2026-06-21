"""
Minimal in-process background scheduler (no extra dependency).
Runs: chat expiry/inactivity sweep every 5 min, daily AI insight once every 24h.
For multi-instance production deployments, run this as a separate worker
process (see `make worker` / docker-compose `worker` service) instead of
inside every API replica.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from app.core.db import async_session_factory
from app.services import ai_insight_service, chat_service

logger = logging.getLogger("livematch.scheduler")

_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_last_insight_date: date | None = None

CHAT_SWEEP_INTERVAL_SECONDS = 5 * 60


async def _sweep_chats_once():
    async with async_session_factory() as session:
        try:
            result = await chat_service.sweep_expired_and_inactive_chats(session)
            await session.commit()
            if result["expired"] or result["inactive"]:
                logger.info("Chat sweep: %s", result)
        except Exception:
            await session.rollback()
            logger.exception("Chat sweep failed")


async def _maybe_generate_daily_insight():
    global _last_insight_date
    today = date.today()
    if _last_insight_date == today:
        return
    async with async_session_factory() as session:
        try:
            await ai_insight_service.generate_daily_insight(session)
            await session.commit()
            _last_insight_date = today
            logger.info("Daily AIInsight generated for %s", today)
        except Exception:
            await session.rollback()
            logger.exception("AIInsight generation failed")


async def _loop():
    assert _stop_event is not None
    while not _stop_event.is_set():
        await _sweep_chats_once()
        await _maybe_generate_daily_insight()
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=CHAT_SWEEP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass


async def start_scheduler():
    global _task, _stop_event
    if _task is not None and not _task.done():
        return
    _stop_event = asyncio.Event()
    _task = asyncio.create_task(_loop())
    logger.info("Background scheduler started")


async def stop_scheduler():
    global _task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _task is not None:
        await _task
    logger.info("Background scheduler stopped")


async def restart_scheduler():
    await stop_scheduler()
    await start_scheduler()
