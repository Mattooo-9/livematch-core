"""/start · /help · /status · /pause — первый экран и системные команды."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.bot.keyboards.main_menu import BTN_PAUSE, BTN_RESUME, BTN_STATUS, main_menu
from app.core.enums import UserState
from app.services import metrics_service, user_service

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session, user, **kwargs):
    # Реферал через ?start=ref_CODE
    if command.args and command.args.startswith("ref_") and user.profile is None:
        from app.services import referral_service
        await referral_service.attribute_referral(
            session, new_user=user, referral_code_used=command.args.removeprefix("ref_")
        )

    has_profile = user.profile is not None
    is_paused = user.state == UserState.PAUSE

    if not has_profile:
        text = (
            "Привет 👋 Это LiveMatch Core.\n\n"
            "Честный сервис знакомств: 1 чат, 24 часа, только живые люди.\n"
            "Без бесконечной ленты. Без ботов. Без покупки внимания.\n\n"
            "→ Создай анкету — займёт 2 минуты."
        )
    else:
        text = f"С возвращением, {user.first_name or 'друг'} 👋"

    await message.answer(text, reply_markup=main_menu(has_profile, is_paused))


@router.message(F.text == "/help")
async def cmd_help(message: Message, **kwargs):
    await message.answer(
        "Как это работает:\n\n"
        "🔎 Найти — анкеты по твоей цели и городу\n"
        "❤️ Лайк → если взаимно → чат на 24ч\n"
        "💬 Чат → 1 активный, 1 в очереди\n"
        "⏳ Продлить → если оба согласны\n\n"
        "Команды: /search · /chat · /status · /verify · /referral · /pay · /community · /events\n"
        "Админам: /admin_report"
    )


@router.message(F.text.in_({"/status", BTN_STATUS}))
async def cmd_status(message: Message, session, user, **kwargs):
    city = user.profile.city if user.profile else None
    p = await metrics_service.pulse(session, city=city)
    parts = [f"📡 Пульс{' · ' + city if city else ''}"]
    parts.append(f"🟢 Онлайн сейчас: {p['online_now']}")
    parts.append(f"💬 Новых чатов за 10 мин: {p['new_chats_last_10_min']}")
    parts.append(f"👥 Активны за 24ч: {p['active_users_24h']}")
    if p['active_users_24h'] == 0:
        parts.append("\nБаза только заполняется — пригласи друзей 🔗")
    await message.answer("\n".join(parts))


@router.message(F.text.in_({"/pause", BTN_PAUSE, BTN_RESUME}))
async def cmd_pause(message: Message, session, user, **kwargs):
    is_paused = user.state == UserState.PAUSE
    if is_paused:
        await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
        await message.answer(
            "▶️ Снова в поиске.\nТебя снова видят.",
            reply_markup=main_menu(has_profile=True, is_paused=False),
        )
    else:
        await user_service.set_state(session, user, UserState.PAUSE)
        await message.answer(
            "⏸ Пауза включена.\nТебя не видно в поиске. Все чаты и матчи сохраняются.",
            reply_markup=main_menu(has_profile=True, is_paused=True),
        )
