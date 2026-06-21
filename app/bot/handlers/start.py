"""/start, /help, /status (pulse), /pause."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message

from app.core.enums import UserState
from app.bot.keyboards.main_menu import main_menu
from app.services import metrics_service, user_service

router = Router(name="start")

WELCOME = (
    "Привет! Это LiveMatch Core 👋\n"
    "Честный сервис знакомств: по цели, району и интересам, без бесконечной ленты.\n\n"
    "Что происходит: ты ещё не создал анкету.\n"
    "Что нажать: «📝 Создать анкету».\n"
    "Что будет дальше: 2 минуты — и ты в поиске."
)

WELCOME_BACK = "С возвращением! Выбирай действие ниже."


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session, user, user_created: bool):
    if user_created and command.args and command.args.startswith("ref_"):
        ref_code = command.args.removeprefix("ref_")
        from app.services import referral_service

        await referral_service.attribute_referral(session, new_user=user, referral_code_used=ref_code)

    if user.profile is None:
        await user_service.set_state(session, user, UserState.PROFILE_CREATION if user.state == UserState.NEW else user.state)
        await message.answer(WELCOME, reply_markup=main_menu(has_profile=False))
    else:
        await message.answer(WELCOME_BACK, reply_markup=main_menu(has_profile=True))


@router.message(F.text == "/help")
async def cmd_help(message: Message, **kwargs):
    await message.answer(
        "Команды:\n"
        "/profile — анкета\n/search — искать\n/next — следующая анкета\n"
        "/status — статус сервиса\n/pause — пауза\n/verify — верификация\n"
        "/referral — рефералка\n/pay — платные возможности\n"
        "/community — комьюнити\n/events — события\n"
        "Кнопка под чатом: 🚨 опасность/мошенничество — только для серьёзных случаев."
    )


@router.message(F.text.in_({"/status", "📊 Статус сервиса"}))
async def cmd_status(message: Message, session, user, **kwargs):
    profile = user.profile
    city = profile.city if profile else None
    p = await metrics_service.pulse(session, city=city)
    text = (
        "📊 Пульс сервиса"
        + (f" — {city}" if city else "")
        + f"\n🟢 Онлайн сейчас: {p['online_now']}"
        + f"\n💬 Новых чатов за 10 мин: {p['new_chats_last_10_min']}"
        + f"\n👥 Активны за 24ч: {p['active_users_24h']}"
    )
    await message.answer(text)


@router.message(F.text.in_({"/pause", "⏸ Пауза"}))
async def cmd_pause(message: Message, session, user, **kwargs):
    if user.state == UserState.PAUSE:
        await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
        await message.answer("Пауза снята. Ты снова виден в поиске.")
    else:
        await user_service.set_state(session, user, UserState.PAUSE)
        await message.answer("Пауза включена. Тебя не видно в поиске, пока не вернёшься.")
