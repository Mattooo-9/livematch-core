"""seed interests and communities

Revision ID: dced5a122506
Revises: 55b74d93d86f
Create Date: 2026-06-21 09:16:13.088443

"""
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dced5a122506'
down_revision = '55b74d93d86f'
branch_labels = None
depends_on = None

CATEGORIES = [
    ("MUSIC", "Музыка", "Music"),
    ("SPORT", "Спорт", "Sport"),
    ("WALKS", "Прогулки", "Walks"),
    ("CINEMA", "Кино", "Cinema"),
    ("GAMES", "Игры", "Games"),
    ("DANCING", "Танцы", "Dancing"),
    ("FOOD", "Еда", "Food"),
    ("BUSINESS", "Бизнес", "Business"),
    ("IT", "IT", "IT"),
    ("ART", "Искусство", "Art"),
    ("NIGHT_CITY", "Ночной город", "Night city"),
    ("TRAVEL", "Путешествия", "Travel"),
    ("ADULT_18", "18+ знакомства", "18+ dating"),
    ("QUICK_MEETUPS", "Быстрые встречи", "Quick meetups"),
    ("VOICE_CHAT", "Голосовое общение", "Voice chat"),
]


def upgrade() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    interests_table = sa.table(
        "interests",
        sa.column("code", sa.String),
        sa.column("category", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("name_en", sa.String),
    )
    op.bulk_insert(
        interests_table,
        [{"code": code, "category": code, "name_ru": ru, "name_en": en} for code, ru, en in CATEGORIES],
    )

    communities_table = sa.table(
        "communities",
        sa.column("code", sa.String),
        sa.column("category", sa.String),
        sa.column("name_ru", sa.String),
        sa.column("name_en", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        communities_table,
        [
            {
                "code": f"community_{code.lower()}",
                "category": code,
                "name_ru": f"{ru}",
                "name_en": en,
                "description": f"Комьюнити по интересу: {ru}",
                "created_at": now,
                "updated_at": now,
            }
            for code, ru, en in CATEGORIES
        ],
    )

    contests_table = sa.table(
        "contests",
        sa.column("type", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.String),
        sa.column("city", sa.String),
        sa.column("starts_at", sa.DateTime),
        sa.column("ends_at", sa.DateTime),
        sa.column("is_active", sa.Boolean),
        sa.column("is_paid", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        contests_table,
        [
            {
                "type": "BEST_DIALOG", "title": "Самый активный честный диалог",
                "description": "Без рейтингов красоты -- только живое честное общение.",
                "city": None, "starts_at": now, "ends_at": now + timedelta(days=7),
                "is_active": True, "is_paid": False, "created_at": now, "updated_at": now,
            },
            {
                "type": "DISTRICT_WALK", "title": "Прогулка по району",
                "description": "Добровольная игровая встреча по интересам в твоём районе.",
                "city": None, "starts_at": now, "ends_at": now + timedelta(days=7),
                "is_active": True, "is_paid": False, "created_at": now, "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM contests WHERE type IN ('BEST_DIALOG', 'DISTRICT_WALK')")
    op.execute("DELETE FROM communities")
    op.execute("DELETE FROM interests")
