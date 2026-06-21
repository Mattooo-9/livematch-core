"""
Bot factory: creates the aiogram Bot + Dispatcher, wires middleware and routers.
Used both by polling entrypoint (scripts/run_bot.py) and by the FastAPI webhook route.
"""
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import build_root_router
from app.bot.middlewares.db_middleware import DbSessionMiddleware
from app.core.config import settings

_bot: Bot | None = None
_dp: Dispatcher | None = None


def _build_storage():
    try:
        from aiogram.fsm.storage.redis import RedisStorage

        return RedisStorage.from_url(settings.REDIS_URL)
    except Exception:
        # Falls back to in-memory FSM storage (fine for single-process local dev,
        # NOT safe for multi-worker production -- make sure Redis is reachable there).
        return MemoryStorage()


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        if not settings.BOT_TOKEN:
            raise RuntimeError("BOT_TOKEN is not set -- check your .env")
        _bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    return _bot


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        _dp = Dispatcher(storage=_build_storage())
        _dp.update.middleware(DbSessionMiddleware())
        _dp.include_router(build_root_router())
    return _dp
