"""FastAPI app: webhook, payments, admin, ai, community, events, webapp API + healthcheck."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routers import admin, community, events, healthcheck, payments_webhook, telegram_webhook, webapp_api
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("livematch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.BOT_USE_WEBHOOK and settings.BOT_TOKEN and settings.BOT_WEBHOOK_URL:
        from app.bot.bot import get_bot

        bot = get_bot()
        url = f"{settings.BOT_WEBHOOK_URL.rstrip('/')}/webhook/telegram/{settings.BOT_WEBHOOK_SECRET}"
        await bot.set_webhook(url, drop_pending_updates=False)
        logger.info("Telegram webhook set: %s", url)

    if settings.RUN_SCHEDULER_IN_API:
        from app.tasks.scheduler import start_scheduler

        await start_scheduler()
    yield

    if settings.RUN_SCHEDULER_IN_API:
        from app.tasks.scheduler import stop_scheduler

        await stop_scheduler()


app = FastAPI(title="LiveMatch Core API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Telegram WebApp is served from a Telegram-controlled webview; tighten in prod if hosting elsewhere
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(healthcheck.router)
app.include_router(telegram_webhook.router)
app.include_router(payments_webhook.router)
app.include_router(admin.router)
app.include_router(community.router)
app.include_router(events.router)
app.include_router(webapp_api.router)

try:
    app.mount("/app", StaticFiles(directory="webapp/static", html=True), name="webapp")
except RuntimeError:
    logger.warning("webapp/ static directory not found -- mini-app static hosting disabled")
