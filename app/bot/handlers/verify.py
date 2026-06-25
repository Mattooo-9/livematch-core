from __future__ import annotations
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from app.bot.states.profile_states import VerificationFlow
from app.core.enums import UserState, VerificationMethod
from app.services import user_service, verification_service

router = Router(name="verify")

GESTURES_RU = {
    "thumbs_up":    "👍 большой палец вверх",
    "peace_sign":   "✌️ знак мира",
    "hand_on_head": "✋ рука на голове",
    "point_left":   "👈 указать влево",
    "point_right":  "👉 указать вправо",
    "wink":         "😉 подмигни",
}


@router.message(F.text == "/verify")
async def cmd_verify(message: Message, state: FSMContext, session, user, **kwargs):
    if user.verification and user.verification.status.value == "APPROVED":
        await message.answer("✅ Верификация уже пройдена. Бейдж в анкете есть.")
        return
    v = await verification_service.start_verification(session, user.id, VerificationMethod.SELFIE_GESTURE)
    await user_service.set_state(session, user, UserState.VERIFICATION)
    await state.set_state(VerificationFlow.awaiting_media)
    gesture = GESTURES_RU.get(v.gesture_code, v.gesture_code)
    await message.answer(
        f"Верификация живого человека.\n\n"
        f"Пришли фото или короткое видео, где ты делаешь: {gesture}\n\n"
        f"Это не хранится публично — только хеш для проверки дубликатов."
    )


@router.message(VerificationFlow.awaiting_media, F.photo | F.video)
async def verify_media(message: Message, state: FSMContext, session, user, **kwargs):
    file_id = message.photo[-1].file_id if message.photo else message.video.file_id
    tg_file = await message.bot.get_file(file_id)
    buf = await message.bot.download_file(tg_file.file_path)
    await verification_service.submit_verification(session, user.id, buf.read())
    await user_service.set_state(session, user, UserState.ACTIVE_SEARCH)
    await state.clear()
    await message.answer("✅ Верифицирован. Бейдж добавлен к анкете.")
