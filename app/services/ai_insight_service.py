"""
AI module — observational/advisory only.
Priority: OpenRouter → Anthropic → OpenAI → rule-based fallback.
"""
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.metrics import AIInsight
from app.services import metrics_service

FALLBACK_NOTE = "(rule-based fallback)"


def _rule_based_summary(metrics: dict) -> str:
    lines = [f"Отчёт за {date.today().isoformat()} {FALLBACK_NOTE}:"]
    lines.append(f"- Новых пользователей за 24ч: {metrics['new_users_24h']}")
    lines.append(f"- Активных за 24ч: {metrics['active_users_24h']}")
    lines.append(f"- Лайки/матчи/чаты: {metrics['likes_24h']}/{metrics['matches_24h']}/{metrics['chats_24h']}")
    lines.append(f"- Пустых чатов: {metrics['empty_chat_pct']}% | Продлений: {metrics['chat_extension_pct']}%")
    lines.append(f"- Платных действий: {metrics['paid_actions_24h']} | Рефералов: {metrics['referrals_activated_24h']}")
    if metrics.get("empty_chat_pct", 0) > 40:
        lines.append("⚠️ Высокий % пустых чатов — проверить качество матчинга.")
    if metrics.get("retention_d1_pct") is not None and metrics["retention_d1_pct"] < 30:
        lines.append("⚠️ Низкий retention D1 — улучшить онбординг.")
    return "\n".join(lines)


PROMPT_TEMPLATE = (
    "Ты product-аналитик дейтинг-сервиса LiveMatch Core. "
    "На основе метрик за 24 часа дай краткий отчёт (5-8 строк, по-русски): "
    "что работает, что ломается, что улучшить, где падает активность. "
    "Метрики: {metrics}"
)


async def _call_openrouter(metrics: dict) -> str | None:
    if not settings.OPENROUTER_API_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://livematch.core",
                    "X-Title": "LiveMatch Core",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-flash-1.5",  # быстрая бесплатная модель на OpenRouter
                    "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(
                        metrics=json.dumps(metrics, ensure_ascii=False)
                    )}],
                    "max_tokens": 600,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"(openrouter error: {e})"


async def _call_anthropic(metrics: dict) -> str | None:
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-haiku-20240307", "max_tokens": 600,
                      "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(metrics=json.dumps(metrics, ensure_ascii=False))}]},
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
    except Exception as e:
        return f"(anthropic error: {e})"


async def _call_openai(metrics: dict) -> str | None:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "Content-Type": "application/json"},
                json={"model": "gpt-4o-mini", "max_tokens": 600,
                      "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(metrics=json.dumps(metrics, ensure_ascii=False))}]},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"(openai error: {e})"


async def _get_ai_summary(metrics: dict) -> str:
    for fn in (_call_openrouter, _call_anthropic, _call_openai):
        result = await fn(metrics)
        if result and "error" not in result:
            return result
    return _rule_based_summary(metrics)


async def generate_daily_insight(session: AsyncSession) -> AIInsight:
    metrics = await metrics_service.daily_aggregate_metrics(session)
    summary = await _get_ai_summary(metrics)
    insight = AIInsight(report_date=date.today(), summary=summary[:4000], details_json=json.dumps(metrics)[:8000])
    session.add(insight)
    await session.flush()
    return insight


def suggest_interests_for_goal(goal: str) -> list[str]:
    mapping = {
        "DATE": ["FOOD", "WALKS", "CINEMA"],
        "FRIENDSHIP": ["SPORT", "GAMES", "TRAVEL"],
        "EVENTS": ["MUSIC", "NIGHT_CITY", "DANCING"],
        "INTERESTS": ["IT", "ART", "BUSINESS"],
    }
    return mapping.get(goal, ["MUSIC", "WALKS", "FOOD"])
