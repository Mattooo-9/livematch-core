"""
Paid feature catalog. Prices are deliberately low and simple ("cheap, clear,
not annoying" per spec). Stars amounts are integer XTR; fiat amounts are minor
units (cents) for Stripe/LiqPay/Fondy/WayForPay.

IMPORTANT: nothing here purchases attractiveness/ranking priority -- see
app/services/matching_service.py, which never reads Payment data.
"""
from __future__ import annotations

from app.core.enums import PaidFeature

# (stars, fiat_cents, human title)
FEATURE_CATALOG: dict[PaidFeature, dict] = {
    PaidFeature.EXTEND_CHAT: {"stars": 15, "fiat_cents": 49, "title_ru": "Продлить чат на 24ч"},
    PaidFeature.EXTRA_LIKES: {"stars": 20, "fiat_cents": 69, "title_ru": "Доп. лайки (10 шт, честный лимит)"},
    PaidFeature.EARLY_ACCESS: {"stars": 25, "fiat_cents": 89, "title_ru": "Ранний доступ к новым анкетам"},
    PaidFeature.EXTENDED_RADIUS: {"stars": 15, "fiat_cents": 49, "title_ru": "Расширенный радиус поиска"},
    PaidFeature.CREATE_COMMUNITY_EVENT: {"stars": 50, "fiat_cents": 199, "title_ru": "Создать закрытое событие/комьюнити"},
    PaidFeature.PAID_CONTEST_ENTRY: {"stars": 20, "fiat_cents": 69, "title_ru": "Участие в платном конкурсе"},
    PaidFeature.INVISIBLE_PAUSE: {"stars": 30, "fiat_cents": 99, "title_ru": "Пауза-невидимость (7 дней)"},
    PaidFeature.EXTENDED_STATS: {"stars": 20, "fiat_cents": 69, "title_ru": "Расширенная статистика активности"},
    PaidFeature.DONATION: {"stars": 50, "fiat_cents": 199, "title_ru": "Донат сервису"},
}
