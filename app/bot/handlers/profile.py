"""Profile creation/edit flow -- intentionally short questionnaire."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core.enums import Gender, Goal, SeekingGender, UserState
from app.bot.keyboards.inline import confirm_kb, gender_kb, goal_kb, interests_kb, seeking_gender_kb, GOAL_LABELS_RU
from app.bot.keyboards.main_menu import main_menu
from app.bot.states.profile_states import ProfileCreation
from app.services import profile_service, user_service, verification_service

router = Router(name="profile")


@router.message(F.text.in_({"/profile", "📝 Создать анкету", "✏️ Изменить анкету"}))
async def start_profile(message: Message, state: FSMContext, session, user, **kwargs):
    await user_service.set_state(session, user, UserState.PROFILE_CREATION)
    await state.set_state(ProfileCreation.city)
    await state.update_data(interests=set())
    await message.answer("Город? (например: Киев)")


@router.message(ProfileCreation.city)
async def step_city(message: Message, state: FSMContext):
    city = (message.text or "").strip()
    if not city or len(city) > 64:
        await message.answer("Введи город текстом (до 64 символов).")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileCreation.district)
    await message.answer("Район? Если неважно — отправь «-»")


@router.message(ProfileCreation.district)
async def step_district(message: Message, state: FSMContext):
    district = (message.text or "").strip()
    await state.update_data(district=None if district == "-" else district)
    await state.set_state(ProfileCreation.age)
    await message.answer("Возраст? (число, 18-99)")


@router.message(ProfileCreation.age)
async def step_age(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    if not raw.isdigit() or not (18 <= int(raw) <= 99):
        await message.answer("Возраст должен быть числом от 18 до 99.")
        return
    await state.update_data(age=int(raw))
    await state.set_state(ProfileCreation.gender)
    await message.answer("Твой пол?", reply_markup=gender_kb())


@router.callback_query(ProfileCreation.gender, F.data.startswith("gender:"))
async def step_gender(call: CallbackQuery, state: FSMContext):
    gender = call.data.split(":", 1)[1]
    await state.update_data(gender=gender)
    await state.set_state(ProfileCreation.seeking_gender)
    await call.message.edit_text(f"Пол: {gender}. Кого ищешь?")
    await call.message.answer("Кого ищешь?", reply_markup=seeking_gender_kb())
    await call.answer()


@router.callback_query(ProfileCreation.seeking_gender, F.data.startswith("seek:"))
async def step_seeking(call: CallbackQuery, state: FSMContext):
    seek = call.data.split(":", 1)[1]
    await state.update_data(seeking_gender=seek)
    await state.set_state(ProfileCreation.goal)
    await call.message.edit_text("Кого ищешь — выбрано.")
    await call.message.answer("Цель знакомства?", reply_markup=goal_kb())
    await call.answer()


@router.callback_query(ProfileCreation.goal, F.data.startswith("goal:"))
async def step_goal(call: CallbackQuery, state: FSMContext):
    goal = call.data.split(":", 1)[1]
    await state.update_data(goal=goal)
    await state.set_state(ProfileCreation.interests)
    await call.message.edit_text(f"Цель: {GOAL_LABELS_RU[Goal(goal)]}")
    await call.message.answer("Выбери 3-10 интересов:", reply_markup=interests_kb(set()))
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
    await state.update_data(interests=selected)
    await call.message.edit_reply_markup(reply_markup=interests_kb(selected))
    await call.answer()


@router.callback_query(ProfileCreation.interests, F.data == "interests_done")
async def step_interests_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = set(data.get("interests", set()))
    if len(selected) < 3:
        await call.answer("Нужно минимум 3 интереса", show_alert=True)
        return
    await state.set_state(ProfileCreation.photo)
    await call.message.edit_text(f"Интересы выбраны: {len(selected)}")
    await call.message.answer("Пришли 1-3 фото (по одному сообщению). Когда закончишь — напиши «готово».")
    await call.answer()


@router.message(ProfileCreation.photo, F.photo)
async def step_photo(message: Message, state: FSMContext, session, user, **kwargs):
    data = await state.get_data()
    photos_count = data.get("photos_count", 0)
    if photos_count >= 3:
        await message.answer("Уже 3 фото — напиши «готово».")
        return
    file = message.photo[-1]
    tg_file = await message.bot.get_file(file.file_id)
    file_bytes_io = await message.bot.download_file(tg_file.file_path)
    image_bytes = file_bytes_io.read()
    await verification_service.add_photo(
        session, user_id=user.id, telegram_file_id=file.file_id, image_bytes=image_bytes, is_primary=(photos_count == 0)
    )
    await state.update_data(photos_count=photos_count + 1)
    await message.answer(f"Фото {photos_count + 1}/3 принято. Ещё фото или напиши «готово».")


@router.message(ProfileCreation.photo, F.text.lower() == "готово")
async def step_photo_done(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("photos_count", 0) < 1:
        await message.answer("Нужно хотя бы 1 фото.")
        return
    await state.set_state(ProfileCreation.confirm)
    await message.answer(
        f"Город: {data['city']}, район: {data.get('district') or '—'}, возраст: {data['age']}\n"
        f"Цель: {GOAL_LABELS_RU[Goal(data['goal'])]}, интересов: {len(data['interests'])}\n"
        "Сохранить анкету?",
        reply_markup=confirm_kb(),
    )


@router.callback_query(ProfileCreation.confirm, F.data == "profile_confirm")
async def step_confirm(call: CallbackQuery, state: FSMContext, session, user, **kwargs):
    data = await state.get_data()
    profile = await profile_service.upsert_profile(
        session,
        user=user,
        city=data["city"],
        district=data.get("district"),
        age=data["age"],
        gender=Gender(data["gender"]),
        seeking_gender=SeekingGender(data["seeking_gender"]),
        goal=Goal(data["goal"]),
    )
    await profile_service.set_interests(session, profile, list(data["interests"]))
    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await state.clear()
    await call.message.edit_text("Анкета сохранена ✅")
    await call.message.answer("Готово! Жми «🔎 Искать», чтобы найти первых людей.", reply_markup=main_menu(has_profile=True))
    await call.answer()
