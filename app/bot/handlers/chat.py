"""
Чат: открытие, ретрансляция, продление, сигнал опасности.

КРИТИЧЕСКОЕ АРХИТЕКТУРНОЕ РЕШЕНИЕ:
Catch-all handler регистрируется ПОСЛЕДНИМ и имеет ФИЛЬТР на активный чат.
Он НЕ срабатывает когда:
- пользователь в FSM-состоянии (ProfileCreation, VerificationFlow, DangerReport)
- сообщение начинается с /
- текст совпадает с кнопкой меню
Это исключает конфликты с другими хендлерами.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import chat_kb
from app.bot.keyboards.main_menu import ALL_MENU_BUTTONS, BTN_CHAT
from app.bot.states.profile_states import DangerReport
from app.models.chat import Chat
from app.models.message import Message as DBMessage
from app.models.user import User
from app.services import chat_service, moderation_service

router = Router(name="chat")


@router.message(F.text.in_({"/chat", BTN_CHAT}))
async def cmd_open_chat(message: Message, session, user, **kwargs):
    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        buffers = await chat_service.get_buffer_chats(session, user.id)
        if buffers:
            await message.answer(
                "Активного чата нет — есть совпадение в очереди.\n"
                "Оно откроется когда текущий чат завершится."
            )
        else:
            await message.answer("Чата пока нет. Найди кого-то → «🔎 Найти».")
        return

    other = await session.get(User, chat.other_user(user.id))
    name = other.first_name or "собеседник" if other else "собеседник"
    from datetime import timezone
    from app.models.mixins import utcnow
    expires = chat.expires_at
    if expires:
        remaining = expires.replace(tzinfo=timezone.utc) - utcnow().replace(tzinfo=timezone.utc)
        hours = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        time_left = f"{hours}ч {mins}м" if hours > 0 else f"{mins}м"
    else:
        time_left = "?"

    await message.answer(
        f"💬 Чат с {name}\n"
        f"Осталось: {time_left}\n\n"
        f"Просто пиши — сообщения уйдут собеседнику.",
        reply_markup=chat_kb(chat.id),
    )


@router.callback_query(F.data.startswith("extend:"))
async def cb_extend(call: CallbackQuery, session, user, **kwargs):
    chat_id = int(call.data.split(":", 1)[1])
    chat = await session.get(Chat, chat_id)
    if not chat or user.id not in (chat.user_a_id, chat.user_b_id):
        await call.answer("Чат не найден.", show_alert=True)
        return

    extended = await chat_service.request_extend(session, chat, user.id)
    if extended:
        other = await session.get(User, chat.other_user(user.id))
        await call.answer("Чат продлён на 24ч ✅", show_alert=True)
        if other:
            try:
                await call.bot.send_message(other.tg_id, "✅ Оба согласились — чат продлён на 24ч.")
            except Exception:
                pass
    else:
        await call.answer("Запрос отправлен. Ждём согласия собеседника.", show_alert=True)


@router.callback_query(F.data.startswith("danger:"))
async def cb_danger_start(call: CallbackQuery, state: FSMContext, **kwargs):
    chat_id = int(call.data.split(":", 1)[1])
    await state.set_state(DangerReport.awaiting_reason)
    await state.update_data(danger_chat_id=chat_id)
    await call.message.answer(
        "🚨 Серьёзный сигнал (только для: мошенничество · угрозы · принуждение · деньги · насилие)\n\n"
        "Опиши кратко что произошло → уйдёт только модераторам, не автобанит."
    )
    await call.answer()


@router.message(DangerReport.awaiting_reason)
async def danger_reason(message: Message, state: FSMContext, session, user, **kwargs):
    data = await state.get_data()
    chat_id = data.get("danger_chat_id")
    chat = await session.get(Chat, chat_id) if chat_id else None
    target_id = chat.other_user(user.id) if chat else None

    await moderation_service.submit_danger_report(
        session, reporter=user,
        target_user_id=target_id,
        chat_id=chat_id,
        reason=(message.text or "")[:500],
    )
    await state.clear()
    await message.answer(
        "Сигнал передан модераторам.\n"
        "Автоматического бана не будет — это живые люди, которые разберутся."
    )


# ── RELAY (регистрируется последним в router) ────────────────────────────────
# Фильтры: только default_state (не в FSM) + не кнопка меню + не команда

@router.message(
    StateFilter(default_state),          # не в FSM-сессии
    ~F.text.startswith("/"),             # не команда
    F.text.func(lambda t: t not in ALL_MENU_BUTTONS),  # не кнопка меню
)
async def relay_message(message: Message, session, user, **kwargs):
    if not message.text:
        return

    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        await message.answer("Чата нет. Сначала найди совпадение → «🔎 Найти».")
        return

    # Антиспам
    if await moderation_service.is_muted(user.id):
        await message.answer("Временная пауза из-за спама. Попробуй через минуту.")
        return
    if not await moderation_service.check_rate_limit(user.id):
        await moderation_service.auto_mute(user.id)
        await message.answer("Слишком быстро. Небольшая пауза.")
        return
    if await moderation_service.check_identical_message_spam(user.id, message.text):
        await moderation_service.auto_mute(user.id)
        await message.answer("Одинаковые сообщения подряд — похоже на спам. Пауза.")
        return

    # Сохраняем и оцениваем
    db_msg = DBMessage(chat_id=chat.id, sender_id=user.id, text=message.text[:4096])
    session.add(db_msg)
    await session.flush()
    risk = await moderation_service.evaluate_message(session, db_msg, chat.id)
    await chat_service.record_message_touch(session, chat)

    # Ретрансляция
    other = await session.get(User, chat.other_user(user.id))
    if other:
        try:
            await message.bot.send_message(other.tg_id, message.text)
        except Exception:
            pass

    # Мягкое предупреждение о риске (без морализаторства)
    if risk >= 0.3:
        await message.answer(
            "⚠️ Похоже, в диалоге речь о деньгах или переводах. "
            "Честный сервис никогда не просит платить собеседнику напрямую."
        )
