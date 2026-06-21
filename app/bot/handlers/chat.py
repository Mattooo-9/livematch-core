"""
Open chat (/chat, кнопка), message relay between the two matched users,
extend-chat, and the hidden danger/scam button.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core.enums import UserState
from app.bot.keyboards.inline import chat_actions_kb
from app.bot.states.profile_states import DangerReport
from app.models.message import Message as MessageModel
from app.models.user import User
from app.services import chat_service, moderation_service, user_service

router = Router(name="chat")


@router.message(F.text.in_({"/chat", "💬 Открыть чат"}))
async def cmd_open_chat(message: Message, session, user, **kwargs):
    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        buffers = await chat_service.get_buffer_chats(session, user.id)
        if buffers:
            await message.answer("Активного чата нет, но есть совпадение в очереди -- оно откроется, как только освободится слот.")
        else:
            await message.answer("Активного чата пока нет. Сначала найди совпадение: «🔎 Искать».")
        return

    await user_service.set_state(session, user, UserState.ACTIVE_CHAT)
    other_id = chat.other_user(user.id)
    other = await session.get(User, other_id)
    name = other.first_name or other.username or "собеседник" if other else "собеседник"
    await message.answer(
        f"Чат с {name} открыт. Просто пиши сюда -- сообщения уйдут собеседнику.\n"
        f"Чат живёт 24ч, можно продлить, если оба согласны.",
        reply_markup=chat_actions_kb(chat.id),
    )


@router.callback_query(F.data.startswith("extend:"))
async def cb_extend(call: CallbackQuery, session, user, **kwargs):
    chat_id = int(call.data.split(":", 1)[1])
    from app.models.chat import Chat

    chat = await session.get(Chat, chat_id)
    if chat is None or user.id not in (chat.user_a_id, chat.user_b_id):
        await call.answer("Чат не найден.", show_alert=True)
        return
    extended = await chat_service.request_extend(session, chat, user.id)
    if extended:
        await call.answer("Чат продлён на 24ч ✅", show_alert=True)
        other_id = chat.other_user(user.id)
        other = await session.get(User, other_id)
        if other:
            try:
                await call.bot.send_message(other.tg_id, "✅ Чат продлён на 24ч -- оба согласились.")
            except Exception:
                pass
    else:
        await call.answer("Запрос на продление отправлен. Ждём согласия собеседника.", show_alert=True)


@router.callback_query(F.data.startswith("danger:"))
async def cb_danger_start(call: CallbackQuery, state: FSMContext, **kwargs):
    chat_id = int(call.data.split(":", 1)[1])
    await state.set_state(DangerReport.awaiting_reason)
    await state.update_data(danger_chat_id=chat_id)
    await call.message.answer(
        "Опиши коротко, что произошло (scam / угрозы / принуждение / деньги / насилие). "
        "Это уйдёт только модераторам, без автобана собеседника."
    )
    await call.answer()


@router.message(DangerReport.awaiting_reason)
async def danger_reason_received(message: Message, state: FSMContext, session, user, **kwargs):
    from app.models.chat import Chat

    data = await state.get_data()
    chat_id = data.get("danger_chat_id")
    chat = await session.get(Chat, chat_id) if chat_id else None
    target_id = chat.other_user(user.id) if chat else None

    await moderation_service.submit_danger_report(
        session, reporter=user, target_user_id=target_id, chat_id=chat_id, reason=message.text or ""
    )
    await state.clear()
    await message.answer("Спасибо, сигнал передан модераторам. Это не приведёт к автоматическому бану.")


@router.message(F.text, ~F.text.startswith("/"))
async def relay_chat_message(message: Message, session, user, **kwargs):
    """Catch-all: if user has an active chat and text isn't a known menu button, relay it."""
    from app.bot.keyboards.main_menu import (
        BTN_COMMUNITY, BTN_CREATE_PROFILE, BTN_EDIT_PROFILE, BTN_EVENTS, BTN_MY_INTERESTS,
        BTN_OPEN_CHAT, BTN_PAID, BTN_PAUSE, BTN_REFERRAL, BTN_SEARCH, BTN_STATUS, BTN_WEBAPP,
    )

    known_buttons = {
        BTN_CREATE_PROFILE, BTN_EDIT_PROFILE, BTN_SEARCH, BTN_PAUSE, BTN_MY_INTERESTS,
        BTN_COMMUNITY, BTN_EVENTS, BTN_REFERRAL, BTN_PAID, BTN_STATUS, BTN_OPEN_CHAT, BTN_WEBAPP,
    }
    if message.text in known_buttons:
        return  # already handled by dedicated handlers registered earlier

    chat = await chat_service.get_active_chat(session, user.id)
    if chat is None:
        await message.answer("У тебя нет активного чата. «🔎 Искать», чтобы найти совпадение, или /help.")
        return

    if await moderation_service.is_muted(user.id):
        await message.answer("Ты временно ограничен в сообщениях из-за спама. Попробуй позже.")
        return
    if not await moderation_service.check_rate_limit(user.id):
        await moderation_service.auto_mute(user.id)
        await message.answer("Слишком много сообщений подряд. Небольшая пауза.")
        return
    if await moderation_service.check_identical_message_spam(user.id, message.text or ""):
        await moderation_service.auto_mute(user.id)
        await message.answer("Похоже на спам (повторяющееся сообщение). Небольшая пауза.")
        return

    db_message = MessageModel(chat_id=chat.id, sender_id=user.id, text=(message.text or "")[:4096])
    session.add(db_message)
    await session.flush()
    risk_score = await moderation_service.evaluate_message(session, db_message, chat.id)
    await chat_service.record_message_touch(session, chat)

    other_id = chat.other_user(user.id)
    other = await session.get(User, other_id)
    if other:
        try:
            await message.bot.send_message(other.tg_id, message.text)
        except Exception:
            pass

    if risk_score >= 0.3:
        await message.answer("⚠️ Похоже, речь про деньги/перевод. Будь осторожен(на) -- сервис никогда не просит платить собеседникам напрямую.")
