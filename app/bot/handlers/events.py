from __future__ import annotations
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.bot.keyboards.main_menu import BTN_EVENTS
from app.services import contest_service

router = Router(name="events")


@router.message(F.text.in_({"/events", BTN_EVENTS}))
async def cmd_events(message: Message, session, user, **kwargs):
    city = user.profile.city if user.profile else None
    contests = await contest_service.list_active_contests(session, city=city)
    if not contests:
        await message.answer("Сейчас активных событий нет. Загляни на неделе — они еженедельные.")
        return
    rows = [
        [InlineKeyboardButton(text=f"🎉 {c.title}", callback_data=f"event:{c.id}")]
        for c in contests
    ]
    await message.answer(
        "🎉 Активные события — добровольные, игровые, без публичных рейтингов красоты.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("event:"))
async def cb_event(call: CallbackQuery, session, user, **kwargs):
    cid = int(call.data.split(":", 1)[1])
    await contest_service.join_contest(session, cid, user.id)
    await call.answer("Записан на событие ✅", show_alert=True)
