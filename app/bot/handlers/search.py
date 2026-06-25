"""
Поиск — показываем ПОЧЕМУ этот человек, не просто карточку.
Алгоритм честный: по интересам, активности, балансу внимания.
Деньги не влияют на выдачу — это проверяется тестом.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.bot.keyboards.inline import GOAL_LABELS, INTEREST_LABELS, candidate_kb
from app.bot.keyboards.main_menu import BTN_SEARCH, main_menu
from app.core.enums import Goal, UserState
from app.models.user import User
from app.services import like_service, matching_service, user_service

router = Router(name="search")


def _match_reason(my_interest_codes: set[str], their_interest_codes: set[str]) -> str:
    """Объясняем совпадение — честно и коротко."""
    common = my_interest_codes & their_interest_codes
    if not common:
        return ""
    labels = [INTEREST_LABELS.get(c, c) for c in list(common)[:2]]
    return " · ".join(labels)


def _candidate_text(profile, match_reason: str) -> str:
    interests = [INTEREST_LABELS.get(ui.interest.code, ui.interest.code) for ui in profile.interests[:5]]
    goal_label = GOAL_LABELS.get(Goal(profile.goal.value), profile.goal.value)
    lines = [
        f"{profile.age} лет · {profile.city}" + (f" · {profile.district}" if profile.district else ""),
        f"Цель: {goal_label}",
    ]
    if interests:
        lines.append("✨ " + " · ".join(interests))
    if profile.bio:
        lines.append(f"\n{profile.bio}")
    if match_reason:
        lines.append(f"\n🎯 Общее: {match_reason}")
    return "\n".join(lines)


async def _show_next(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    queue: list[int] = data.get("sq", [])

    if not queue:
        candidates = await matching_service.find_candidates(session, user, limit=10)
        queue = [p.user_id for p in candidates]
        await state.update_data(sq=queue)

    if not queue:
        await message.answer(
            "Пока нет новых анкет по твоим параметрам.\n"
            "Попробуй чуть позже — база живая."
        )
        return

    cid = queue.pop(0)
    await state.update_data(sq=queue)

    res = await session.execute(select(User).where(User.id == cid))
    candidate = res.scalar_one_or_none()
    if not candidate or not candidate.profile:
        await _show_next(message, state, session, user)
        return

    profile = candidate.profile
    my_codes = {ui.interest.code for ui in user.profile.interests} if user.profile else set()
    their_codes = {ui.interest.code for ui in profile.interests}
    reason = _match_reason(my_codes, their_codes)
    text = _candidate_text(profile, reason)
    kb = candidate_kb(cid, f"+{len(my_codes & their_codes)}" if (my_codes & their_codes) else "")

    if candidate.photos:
        await message.answer_photo(
            candidate.photos[0].telegram_file_id,
            caption=text,
            reply_markup=kb,
        )
    else:
        await message.answer(text, reply_markup=kb)


@router.message(F.text.in_({"/search", "/next", BTN_SEARCH}))
async def cmd_search(message: Message, state: FSMContext, session, user, **kwargs):
    if not user.profile:
        await message.answer("Сначала создай анкету — кнопка «📝 Создать анкету».")
        return
    if user.state == UserState.PAUSE:
        await message.answer("Ты на паузе. Нажми «▶️ Продолжить поиск» чтобы снова искать.")
        return
    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await _show_next(message, state, session, user)


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    uid = int(call.data.split(":", 1)[1])
    await like_service.record_skip(session, user, uid)
    await call.message.edit_reply_markup(reply_markup=None)
    await _show_next(call.message, state, session, user)
    await call.answer()


@router.callback_query(F.data.startswith("like:"))
async def cb_like(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    uid = int(call.data.split(":", 1)[1])
    try:
        _, match = await like_service.record_like(session, user, uid)
    except like_service.LikeLimitReached as e:
        budget = str(e).split(":")[-1]
        await call.answer(f"Лимит лайков на сегодня ({budget}). Разблокировать → ⭐ Возможности.", show_alert=True)
        return
    except ValueError:
        await call.answer("Уже лайкнуто.", show_alert=True)
        return

    await call.message.edit_reply_markup(reply_markup=None)

    if match:
        await user_service.set_state(session, user, UserState.ACTIVE_CHAT)
        # Получаем общие интересы для ice-breaker
        res = await session.execute(select(User).where(User.id == uid))
        other = res.scalar_one_or_none()
        my_codes = {ui.interest.code for ui in user.profile.interests} if user.profile else set()
        their_codes = {ui.interest.code for ui in other.profile.interests} if other and other.profile else set()
        common = my_codes & their_codes
        common_text = " и ".join(INTEREST_LABELS.get(c, c) for c in list(common)[:2]) if common else ""
        
        match_msg = "🎉 Взаимно!\n\nЧат открыт на 24 часа."
        if common_text:
            match_msg += f"\n\nВас объединяет: {common_text} — хороший старт."
        match_msg += "\n\nНажми «💬 Мой чат»."
        
        await call.message.answer(match_msg, reply_markup=main_menu(has_profile=True))
        
        if other:
            try:
                their_common = " и ".join(INTEREST_LABELS.get(c, c) for c in list(common)[:2]) if common else ""
                notify = f"🎉 Взаимно!\n\nЧат открыт на 24 часа."
                if their_common:
                    notify += f"\n\nВас объединяет: {their_common}."
                notify += "\n\nНажми «💬 Мой чат»."
                await call.bot.send_message(other.tg_id, notify)
            except Exception:
                pass
        await call.answer("Матч! 🎉")
    else:
        await call.answer("Лайк отправлен ❤️")
        await _show_next(call.message, state, session, user)
