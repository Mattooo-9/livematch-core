"""/admin_report -- admin-only daily report (metrics + AI insight)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import func, select

from app.core.enums import ModerationStatus
from app.models.moderation import ModerationQueueItem
from app.services import ai_insight_service, metrics_service

router = Router(name="admin")


@router.message(F.text == "/admin_report")
async def cmd_admin_report(message: Message, session, user, **kwargs):
    if not user.is_admin:
        await message.answer("Команда только для администраторов.")
        return

    metrics = await metrics_service.daily_aggregate_metrics(session)
    insight = await ai_insight_service.generate_daily_insight(session)

    open_signals = (
        await session.execute(
            select(func.count(ModerationQueueItem.id)).where(ModerationQueueItem.status == ModerationStatus.OPEN)
        )
    ).scalar_one()

    text = (
        f"📋 Отчёт за {insight.report_date}\n\n"
        f"Новые: {metrics['new_users_24h']} | Активные 24ч: {metrics['active_users_24h']}\n"
        f"Лайки/Матчи/Чаты: {metrics['likes_24h']}/{metrics['matches_24h']}/{metrics['chats_24h']}\n"
        f"Пустых чатов: {metrics['empty_chat_pct']}% | Продлений: {metrics['chat_extension_pct']}%\n"
        f"Платных действий: {metrics['paid_actions_24h']} | Активир. рефералов: {metrics['referrals_activated_24h']}\n"
        f"Retention D1/D7: {metrics['retention_d1_pct']}% / {metrics['retention_d7_pct']}%\n"
        f"Открытых сигналов модерации: {open_signals}\n\n"
        f"🤖 AI-резюме:\n{insight.summary}"
    )
    await message.answer(text)
