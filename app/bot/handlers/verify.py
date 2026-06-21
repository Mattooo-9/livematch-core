"""/verify -- selfie-gesture challenge + perceptual-hash dedup (see verification_service for scope notes)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.profile_states import VerificationFlow
from app.core.enums import UserState, VerificationMethod
from app.services import user_service, verification_service

router = Router(name="verify")

GESTURE_LABELS = {
    "thumbs_up": "👍 большой палец вверх",
    "peace_sign": "✌️ знак виктория",
    "hand_on_head": "✋ рука на голове",
    "point_left": "👈 указать влево",
    "point_right": "👉 указать вправо",
    "wink": "😉 подмигнуть",
}


@router.message(F.text == "/verify")
async def cmd_verify(message: Message, state: FSMContext, session, user, **kwargs):
    v = await verification_service.start_verification(session, user.id, VerificationMethod.SELFIE_GESTURE)
    await user_service.set_state(session, user, UserState.VERIFICATION)
    await state.set_state(VerificationFlow.awaiting_media)
    gesture_label = GESTURE_LABELS.get(v.gesture_code, v.gesture_code)
    await message.answer(f"Пришли короткое фото/видео, где ты делаешь: {gesture_label}")


@router.message(VerificationFlow.awaiting_media, F.photo | F.video)
async def verify_media_received(message: Message, state: FSMContext, session, user, **kwargs):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    tg_file = await message.bot.get_file(file_id)
    buf = await message.bot.download_file(tg_file.file_path)
    file_bytes = buf.read()

    await verification_service.submit_verification(session, user.id, file_bytes)
    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await state.clear()
    await message.answer("Верификация пройдена ✅ Бейдж добавлен к анкете.")
