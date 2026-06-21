"""/events -- weekly voluntary mini-events, no public beauty rankings."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.services import contest_service

router = Router(name="events")


@router.message(F.text.in_({"/events", "🎉 События"}))
async def cmd_events(message: Message, session, user, **kwargs):
    city = user.profile.city if user.profile else None
    contests = await contest_service.list_active_contests(session, city=city)
    if not contests:
        await message.answer("Сейчас активных событий нет. Загляни на неделе -- они еженедельные.")
        return
    rows = [[InlineKeyboardButton(text=f"🎉 {c.title}", callback_data=f"join_event:{c.id}")] for c in contests]
    await message.answer("Активные события:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("join_event:"))
async def cb_join_event(call: CallbackQuery, session, user, **kwargs):
    contest_id = int(call.data.split(":", 1)[1])
    await contest_service.join_contest(session, contest_id, user.id)
    await call.answer("Записал тебя на событие ✅", show_alert=True)
