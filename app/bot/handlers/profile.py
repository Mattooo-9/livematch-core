"""
Анкета — FSM с 6 шагами. Максимально коротко, без лишних слов.
Каждый экран отвечает: что сейчас · что нажать · что дальше.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards.inline import (
    GOAL_LABELS, INTEREST_LABELS, confirm_kb,
    gender_kb, goal_kb, interests_kb, seeking_kb,
)
from app.bot.keyboards.main_menu import BTN_CREATE, BTN_EDIT, main_menu
from app.bot.states.profile_states import ProfileCreation
from app.core.enums import Gender, Goal, SeekingGender, UserState
from app.services import profile_service, user_service, verification_service

router = Router(name="profile")


@router.message(F.text.in_({"/profile", BTN_CREATE, BTN_EDIT}))
async def start_profile(message: Message, state: FSMContext, session, user, **kwargs):
    await user_service.set_state(session, user, UserState.PROFILE_CREATION)
    # Предзаполняем если анкета уже есть
    existing = user.profile
    await state.set_state(ProfileCreation.city)
    await state.update_data(
        interests=set(ui.interest.code for ui in existing.interests) if existing else set(),
        photos_count=len(user.photos) if user.photos else 0,
    )
    hint = f" (сейчас: {existing.city})" if existing else ""
    await message.answer(f"Город{hint}?\n\nНапример: Киев")


@router.message(ProfileCreation.city)
async def step_city(message: Message, state: FSMContext):
    city = (message.text or "").strip()[:64]
    if len(city) < 2:
        await message.answer("Введи название города.")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileCreation.district)
    await message.answer(f"Район в {city}?\n\nЕсли неважно — «-»")


@router.message(ProfileCreation.district)
async def step_district(message: Message, state: FSMContext):
    district = (message.text or "").strip()
    await state.update_data(district=None if district in ("-", "—", "нет") else district[:64])
    await state.set_state(ProfileCreation.age)
    await message.answer("Возраст?\n\nЧисло, 18–99")


@router.message(ProfileCreation.age)
async def step_age(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (18 <= int(raw) <= 99):
        await message.answer("Введи число от 18 до 99.")
        return
    await state.update_data(age=int(raw))
    await state.set_state(ProfileCreation.gender)
    await message.answer("Твой пол?", reply_markup=gender_kb())


@router.callback_query(ProfileCreation.gender, F.data.startswith("gender:"))
async def step_gender(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":", 1)[1]
    await state.update_data(gender=gender)
    await state.set_state(ProfileCreation.seeking_gender)
    await call.message.edit_text(f"Пол: выбрано ✓")
    await call.message.answer("Кого ищешь?", reply_markup=seeking_kb())
    await call.answer()


@router.callback_query(ProfileCreation.seeking_gender, F.data.startswith("seek:"))
async def step_seeking(call: CallbackQuery, state: FSMContext):
    await state.update_data(seeking_gender=call.data.split(":", 1)[1])
    await state.set_state(ProfileCreation.goal)
    await call.message.edit_text("Кого ищешь: выбрано ✓")
    await call.message.answer("Цель знакомства?", reply_markup=goal_kb())
    await call.answer()


@router.callback_query(ProfileCreation.goal, F.data.startswith("goal:"))
async def step_goal(call: CallbackQuery, state: FSMContext):
    goal_val = call.data.split(":", 1)[1]
    await state.update_data(goal=goal_val)
    await state.set_state(ProfileCreation.interests)
    data = await state.get_data()
    selected = set(data.get("interests", set()))
    await call.message.edit_text(f"Цель: {GOAL_LABELS[Goal(goal_val)]} ✓")
    await call.message.answer(
        "Интересы — выбери от 3 до 10.\n\nЭто главной сигнал совместимости.",
        reply_markup=interests_kb(selected),
    )
    await call.answer()


@router.callback_query(ProfileCreation.interests, F.data.startswith("int:"))
async def step_interest_toggle(call: CallbackQuery, state: FSMContext):
    code = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected: set = set(data.get("interests", set()))
    if code in selected:
        selected.discard(code)
    elif len(selected) < 10:
        selected.add(code)
    else:
        await call.answer("Максимум 10 интересов", show_alert=True)
        return
    await state.update_data(interests=selected)
    await call.message.edit_reply_markup(reply_markup=interests_kb(selected))
    await call.answer()


@router.callback_query(ProfileCreation.interests, F.data == "interests_done")
async def step_interests_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if len(set(data.get("interests", set()))) < 3:
        await call.answer("Нужно минимум 3 интереса", show_alert=True)
        return
    await state.set_state(ProfileCreation.photo)
    await call.message.edit_text(f"Интересы выбраны ✓")
    photos_count = data.get("photos_count", 0)
    if photos_count > 0:
        await call.message.answer(
            f"Фото: уже {photos_count} загружено.\n\nПришли новое чтобы заменить, или напиши «дальше»."
        )
    else:
        await call.message.answer(
            "Фото — пришли 1–3 фото.\n\nКогда готово → напиши «дальше».\nФото влияет только на первое впечатление, не на алгоритм."
        )
    await call.answer()


@router.message(ProfileCreation.photo, F.photo)
async def step_photo(message: Message, state: FSMContext, session, user, **kwargs):
    data = await state.get_data()
    count = data.get("photos_count", 0)
    if count >= 3:
        await message.answer("Уже 3 фото. Напиши «дальше».")
        return
    file = message.photo[-1]
    tg_file = await message.bot.get_file(file.file_id)
    buf = await message.bot.download_file(tg_file.file_path)
    await verification_service.add_photo(
        session, user_id=user.id, telegram_file_id=file.file_id,
        image_bytes=buf.read(), is_primary=(count == 0),
    )
    count += 1
    await state.update_data(photos_count=count)
    hint = "Ещё можно " + str(3 - count) + "." if count < 3 else "Максимум."
    await message.answer(f"Фото {count}/3 ✓ {hint} Или напиши «дальше».")


@router.message(ProfileCreation.photo, F.text.lower().in_({"дальше", "готово", "next", "-"}))
async def step_photo_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("photos_count", 0) < 1:
        await message.answer("Нужно хотя бы одно фото.")
        return
    await _show_confirm(message, state, data)


async def _show_confirm(message: Message, state: FSMContext, data: dict):
    from app.bot.keyboards.inline import GOAL_LABELS
    interests_text = ", ".join(
        INTEREST_LABELS.get(c, c) for c in list(data.get("interests", []))[:5]
    )
    await state.set_state(ProfileCreation.confirm)
    await message.answer(
        f"Проверь анкету:\n\n"
        f"📍 {data['city']}" + (f" / {data['district']}" if data.get('district') else "") + "\n"
        f"👤 {data['age']} лет\n"
        f"🎯 Цель: {GOAL_LABELS.get(Goal(data['goal']), data['goal'])}\n"
        f"✨ Интересы: {interests_text}\n"
        f"📸 Фото: {data.get('photos_count', 0)} шт.\n\n"
        f"Сохранить?",
        reply_markup=confirm_kb(),
    )


@router.callback_query(ProfileCreation.confirm, F.data == "profile_edit")
async def step_edit(call: CallbackQuery, state: FSMContext):
    await state.set_state(ProfileCreation.city)
    await call.message.edit_text("Изменяем. Город?")
    await call.answer()


@router.callback_query(ProfileCreation.confirm, F.data == "profile_confirm")
async def step_confirm(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    data = await state.get_data()
    try:
        profile = await profile_service.upsert_profile(
            session, user=user,
            city=data["city"], district=data.get("district"),
            age=data["age"],
            gender=Gender(data["gender"]),
            seeking_gender=SeekingGender(data["seeking_gender"]),
            goal=Goal(data["goal"]),
        )
        await profile_service.set_interests(session, profile, list(data.get("interests", [])))
    except profile_service.ProfileValidationError as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)
        return

    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await state.clear()
    await call.message.edit_text("Анкета сохранена ✅")
    await call.message.answer(
        "Готово. Нажми «🔎 Найти» — покажем людей рядом с похожими интересами.",
        reply_markup=main_menu(has_profile=True, is_paused=False),
    )
    await call.answer()
