"""/referral -- link + simple stats."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select

from app.core.config import settings
from app.core.enums import ReferralStatus
from app.models.referral import Referral

router = Router(name="referral")


@router.message(F.text.in_({"/referral", "🔗 Рефералка"}))
async def cmd_referral(message: Message, session, user, **kwargs):
    bot_username = (await message.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{user.referral_code}"

    total = (await session.execute(select(func.count(Referral.id)).where(Referral.referrer_id == user.id))).scalar_one()
    activated = (
        await session.execute(
            select(func.count(Referral.id)).where(Referral.referrer_id == user.id, Referral.status == ReferralStatus.ACTIVATED)
        )
    ).scalar_one()

    await message.answer(
        f"Твоя ссылка:\n{link}\n\n"
        f"Приглашено: {total} | Активировано: {activated}\n"
        f"За каждого активного друга: +{settings.REFERRAL_INVITER_BONUS_LIKES} лайков тебе, "
        f"+{settings.REFERRAL_INVITED_BONUS_LIKES} другу.\n"
        "Засчитывается только после того, как друг создаст анкету и сделает первое действие."
    )
