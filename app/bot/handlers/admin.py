from __future__ import annotations
from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select
from app.core.enums import ModerationStatus
from app.models.moderation import ModerationQueueItem
from app.services import ai_insight_service, metrics_service

router = Router(name="admin")


@router.message(F.text == "/admin_report")
async def cmd_admin(message: Message, session, user, **kwargs):
    if not user.is_admin:
        await message.answer("Только для администраторов.")
        return
    m = await metrics_service.daily_aggregate_metrics(session)
    insight = await ai_insight_service.generate_daily_insight(session)
    open_q = (await session.execute(
        select(func.count(ModerationQueueItem.id)).where(ModerationQueueItem.status == ModerationStatus.OPEN)
    )).scalar_one()

    await message.answer(
        f"📋 Отчёт {insight.report_date}\n\n"
        f"Новые: {m['new_users_24h']} | Активные: {m['active_users_24h']}\n"
        f"Лайки/Матчи/Чаты: {m['likes_24h']}/{m['matches_24h']}/{m['chats_24h']}\n"
        f"Пустых чатов: {m['empty_chat_pct']}% | Продлений: {m['chat_extension_pct']}%\n"
        f"Платных действий: {m['paid_actions_24h']}\n"
        f"Retention D1/D7: {m['retention_d1_pct']}% / {m['retention_d7_pct']}%\n"
        f"Сигналов модерации: {open_q}\n\n"
        f"🤖 AI:\n{insight.summary}"
    )
