"""/search, /next, like/skip callbacks -- one candidate at a time, no infinite feed."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from app.core.enums import Goal, UserState
from app.bot.keyboards.inline import GOAL_LABELS_RU, candidate_actions_kb
from app.models.user import User
from app.services import like_service, matching_service, user_service

router = Router(name="search")


def _candidate_caption(profile) -> str:
    interests = ", ".join(ui.interest.name_ru for ui in profile.interests[:5])
    return (
        f"{profile.age}, {profile.city}" + (f" / {profile.district}" if profile.district else "")
        + f"\nЦель: {GOAL_LABELS_RU.get(Goal(profile.goal.value), profile.goal.value)}"
        + f"\nИнтересы: {interests}"
        + (f"\n{profile.bio}" if profile.bio else "")
    )


async def _send_next_candidate(message: Message, state: FSMContext, session, user) -> None:
    data = await state.get_data()
    queue: list[int] = data.get("search_queue", [])

    if not queue:
        candidates = await matching_service.find_candidates(session, user, limit=10)
        queue = [p.user_id for p in candidates]
        await state.update_data(search_queue=queue)

    if not queue:
        await message.answer("Сейчас новых анкет нет. Загляни чуть позже -- база живая и постоянно обновляется.")
        return

    next_user_id = queue.pop(0)
    await state.update_data(search_queue=queue)

    res = await session.execute(select(User).where(User.id == next_user_id))
    candidate_user = res.scalar_one_or_none()
    if candidate_user is None or candidate_user.profile is None:
        await _send_next_candidate(message, state, session, user)
        return

    profile = candidate_user.profile
    caption = _candidate_caption(profile)
    kb = candidate_actions_kb(next_user_id)

    if candidate_user.photos:
        await message.answer_photo(candidate_user.photos[0].telegram_file_id, caption=caption, reply_markup=kb)
    else:
        await message.answer(caption, reply_markup=kb)


@router.message(F.text.in_({"/search", "🔎 Искать", "/next"}))
async def cmd_search(message: Message, state: FSMContext, session, user, **kwargs):
    if user.profile is None:
        await message.answer("Сначала создай анкету: «📝 Создать анкету».")
        return
    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await _send_next_candidate(message, state, session, user)


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    target_id = int(call.data.split(":", 1)[1])
    await like_service.record_skip(session, user, target_id)
    await call.message.edit_reply_markup(reply_markup=None)
    await _send_next_candidate(call.message, state, session, user)
    await call.answer()


@router.callback_query(F.data.startswith("like:"))
async def cb_like(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    target_id = int(call.data.split(":", 1)[1])
    try:
        like, match = await like_service.record_like(session, user, target_id)
    except like_service.LikeLimitReached:
        await call.answer("Лимит лайков на сегодня исчерпан. Можно расширить через ⭐ Платные возможности.", show_alert=True)
        return
    except ValueError:
        await call.answer("Уже лайкнуто.", show_alert=True)
        return

    await call.message.edit_reply_markup(reply_markup=None)

    if match:
        await user_service.set_state(session, user, UserState.ACTIVE_CHAT)
        await call.message.answer("🎉 Это матч! Открой чат: /chat или кнопкой «💬 Открыть чат».")
        target_user = await session.get(User, target_id)
        if target_user:
            try:
                await call.bot.send_message(
                    target_user.tg_id, "🎉 У тебя матч! Открой чат: /chat или кнопкой «💬 Открыть чат»."
                )
            except Exception:
                pass
    else:
        await call.answer("Лайк отправлен ❤️")

    await _send_next_candidate(call.message, state, session, user)
