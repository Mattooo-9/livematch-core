"""
AI module -- a separate service layer, strictly observational/advisory.

Hard rules enforced by design here:
- this module NEVER sends messages on behalf of a user
- this module NEVER fabricates activity numbers shown to users (pulse numbers
  come straight from metrics_service, untouched)
- this module NEVER pretends to be a human in chat

It produces: daily AIInsight reports, lightweight profile-improvement tips,
interest suggestions, and event ideas -- all clearly advisory, all logged.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.metrics import AIInsight
from app.services import metrics_service

FALLBACK_NOTE = "(rule-based fallback -- set ANTHROPIC_API_KEY for richer AI analysis)"


def _rule_based_summary(metrics: dict) -> str:
    lines = [f"Отчёт за {date.today().isoformat()} {FALLBACK_NOTE}:"]
    lines.append(f"- Новых пользователей за 24ч: {metrics['new_users_24h']}")
    lines.append(f"- Активных за 24ч: {metrics['active_users_24h']}")
    lines.append(f"- Лайков/матчей/чатов: {metrics['likes_24h']}/{metrics['matches_24h']}/{metrics['chats_24h']}")
    lines.append(f"- Пустых чатов: {metrics['empty_chat_pct']}% | Продлений: {metrics['chat_extension_pct']}%")
    lines.append(f"- Платных действий: {metrics['paid_actions_24h']} | Активированных рефералов: {metrics['referrals_activated_24h']}")
    lines.append(f"- Средний risk_score: {metrics['avg_risk_score']} | spam_score: {metrics['avg_spam_score']}")
    if metrics["empty_chat_pct"] and metrics["empty_chat_pct"] > 40:
        lines.append("⚠️ Высокий процент пустых чатов -- проверить качество подбора и онбординг анкеты.")
    if metrics["retention_d1_pct"] is not None and metrics["retention_d1_pct"] < 30:
        lines.append("⚠️ Низкий retention D1 -- усилить первый день (быстрый первый матч, понятный онбординг).")
    return "\n".join(lines)


async def _call_anthropic(metrics: dict) -> str | None:
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import httpx

        prompt = (
            "Ты product-аналитик дейтинг-сервиса LiveMatch Core. "
            "На основе метрик за последние 24 часа дай краткий отчёт (5-8 строк, по-русски): "
            "что работает, что ломается, что улучшить, где падает активность, что изменить в алгоритме. "
            f"Метрики: {json.dumps(metrics, ensure_ascii=False)}"
        )
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.AI_MODEL,
                    "max_tokens": 600,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
            return "\n".join(text_blocks) if text_blocks else None
    except Exception as e:  # noqa: BLE001 -- AI module must never crash the app
        return f"(AI call failed: {e}; falling back to rule-based summary)"


async def generate_daily_insight(session: AsyncSession) -> AIInsight:
    metrics = await metrics_service.daily_aggregate_metrics(session)
    ai_summary = await _call_anthropic(metrics)
    summary = ai_summary if (ai_summary and "AI call failed" not in ai_summary) else _rule_based_summary(metrics)

    insight = AIInsight(report_date=date.today(), summary=summary[:4000], details_json=json.dumps(metrics)[:8000])
    session.add(insight)
    await session.flush()
    return insight


def suggest_interests_for_goal(goal: str) -> list[str]:
    """Simple heuristic interest suggestions -- no ML needed for an honest hint."""
    mapping = {
        "DATE": ["FOOD", "WALKS", "CINEMA"],
        "FRIENDSHIP": ["SPORT", "GAMES", "TRAVEL"],
        "EVENTS": ["MUSIC", "NIGHT_CITY", "DANCING"],
        "INTERESTS": ["IT", "ART", "BUSINESS"],
    }
    return mapping.get(goal, ["MUSIC", "WALKS", "FOOD"])
