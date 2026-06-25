from __future__ import annotations
from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from app.bot.keyboards.main_menu import BTN_REF
from app.core.config import settings
from app.core.enums import ReferralStatus
from app.models.referral import Referral

router = Router(name="referral")


@router.message(F.text.in_({"/referral", BTN_REF}))
async def cmd_referral(message: Message, session, user, **kwargs):
    bot = await message.bot.get_me()
    link = f"https://t.me/{bot.username}?start=ref_{user.referral_code}"
    total = (await session.execute(
        select(func.count(Referral.id)).where(Referral.referrer_id == user.id)
    )).scalar_one()
    active = (await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == user.id, Referral.status == ReferralStatus.ACTIVATED
        )
    )).scalar_one()

    await message.answer(
        f"🔗 Твоя ссылка:\n{link}\n\n"
        f"Приглашено: {total} · Активировали анкету: {active}\n\n"
        f"За каждого активного друга:\n"
        f"→ тебе +{settings.REFERRAL_INVITER_BONUS_LIKES} лайков\n"
        f"→ другу +{settings.REFERRAL_INVITED_BONUS_LIKES} лайков\n\n"
        f"Считается только после того, как друг заполнит анкету и сделает первое действие."
    )
