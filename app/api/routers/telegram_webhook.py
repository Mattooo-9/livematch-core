"""Telegram bot webhook endpoint (production mode). Secret token is in the URL path."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from aiogram.types import Update

from app.bot.bot import get_bot, get_dispatcher
from app.core.config import settings

router = APIRouter(tags=["telegram"])


@router.post("/webhook/telegram/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != settings.BOT_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="invalid_webhook_secret")

    data = await request.json()
    update = Update.model_validate(data)
    bot = get_bot()
    dp = get_dispatcher()
    await dp.feed_update(bot, update)
    return {"ok": True}
