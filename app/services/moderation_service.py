"""
Antispam (Redis-based) + anti-fraud risk detection + moderation queue.

Design choices from spec:
- no manual complaints as the main mechanic
- a hidden "danger" button exists only for serious cases (scam/threats/coercion/money/violence)
- such signals NEVER auto-ban -- they always land in moderation_queue for a human
- risky keyword dialogs (payment requests, crypto, "pay for intimacy", investments, bets)
  get a soft in-chat warning + logged risk_score, also queued for moderation
"""
from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ModerationSignalType
from app.core.redis_client import safe_redis
from app.models.message import Message
from app.models.moderation import ModerationQueueItem
from app.models.user import User

# Intentionally simple keyword/regex based heuristic -- production should add a
# proper classifier, but this gives real, working risk_score signal today.
RISK_PATTERNS = [
    r"\bпредоплат\w*",
    r"\bоплат\w*\s+(вперед|вперёд|сначала)",
    r"\bперевед\w*\s+деньги",
    r"\bкарт\w*\s+\d{4}",
    r"\bкрипт\w*",
    r"\bбиткоин\w*",
    r"\bbitcoin\b|\bbtc\b|\busdt\b|\bкошел[её]к\s+крипт\w*",
    r"\bинвестиц\w*",
    r"\bставк\w*\s+(на спорт|в букмекер)",
    r"\bинтим\w*\s+за\s+деньги",
    r"\bсекс\w*\s+за\s+деньги",
    r"\bвебкам\b",
    r"\bonlyfans\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in RISK_PATTERNS]


def detect_risk_score(text: str) -> float:
    hits = sum(1 for pattern in _COMPILED if pattern.search(text))
    if hits == 0:
        return 0.0
    return min(1.0, 0.3 + hits * 0.25)


async def check_rate_limit(user_id: int) -> bool:
    """Returns True if user is within the per-minute message limit."""
    redis = await safe_redis()
    minute_bucket = f"msg_rate:{user_id}"
    count = await redis.incr(minute_bucket)
    if count == 1:
        await redis.expire(minute_bucket, 60)
    return count <= settings.MESSAGES_PER_MINUTE_LIMIT


async def check_identical_message_spam(user_id: int, text: str) -> bool:
    """Returns True if this exact text was already sent too many times recently (=> spam)."""
    redis = await safe_redis()
    normalized = text.strip().lower()[:256]
    key = f"msg_dup:{user_id}:{hash(normalized)}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, 60 * 10)
    return count > settings.IDENTICAL_MESSAGE_LIMIT


async def auto_mute(user_id: int, seconds: int = 600) -> None:
    redis = await safe_redis()
    await redis.setex(f"muted:{user_id}", seconds, "1")


async def is_muted(user_id: int) -> bool:
    redis = await safe_redis()
    val = await redis.get(f"muted:{user_id}")
    return val is not None


async def evaluate_message(session: AsyncSession, message: Message, chat_id: int) -> float:
    """Scores a persisted message, flags it + queues moderation if risky."""
    score = detect_risk_score(message.text)
    message.risk_score = score
    if score >= 0.3:
        message.is_flagged = True
        session.add(
            ModerationQueueItem(
                signal_type=ModerationSignalType.RISK_KEYWORDS,
                target_user_id=message.sender_id,
                chat_id=chat_id,
                message_id=message.id,
                reason=f"auto risk_score={score:.2f}",
            )
        )
    await session.flush()
    return score


async def submit_danger_report(
    session: AsyncSession, reporter: User, target_user_id: int, chat_id: int | None, reason: str
) -> ModerationQueueItem:
    item = ModerationQueueItem(
        signal_type=ModerationSignalType.DANGER_BUTTON,
        reporter_user_id=reporter.id,
        target_user_id=target_user_id,
        chat_id=chat_id,
        reason=reason[:500],
    )
    session.add(item)
    reporter.risk_score = reporter.risk_score  # unaffected -- reporting never penalizes reporter
    target = await session.get(User, target_user_id)
    if target:
        target.risk_score = min(10.0, target.risk_score + 1.0)
    await session.flush()
    return item
