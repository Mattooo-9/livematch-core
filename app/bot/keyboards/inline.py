"""Все inline-клавиатуры в одном файле."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.core.enums import Gender, Goal, SeekingGender

# ── Цели ─────────────────────────────────────────────────────────────────────
GOAL_LABELS = {
    Goal.COMMUNICATION: "💬 Общение",
    Goal.DATE:          "☕ Свидание",
    Goal.INTIMATE:      "🔥 Секс",
    Goal.REGULAR:       "🔄 Регулярное",
    Goal.FRIENDSHIP:    "🤝 Дружба",
    Goal.INTERESTS:     "🎯 Интересы",
    Goal.EVENTS:        "🎉 События",
}

# ── Интересы ──────────────────────────────────────────────────────────────────
INTEREST_LABELS = {
    "MUSIC":        "🎵 Музыка",
    "SPORT":        "🏃 Спорт",
    "WALKS":        "🚶 Прогулки",
    "CINEMA":       "🎬 Кино",
    "GAMES":        "🎮 Игры",
    "DANCING":      "💃 Танцы",
    "FOOD":         "🍜 Еда",
    "BUSINESS":     "💼 Бизнес",
    "IT":           "💻 IT",
    "ART":          "🎨 Искусство",
    "NIGHT_CITY":   "🌃 Ночной город",
    "TRAVEL":       "✈️ Путешествия",
    "ADULT_18":     "🔞 18+",
    "QUICK_MEETUPS":"⚡ Быстрые встречи",
    "VOICE_CHAT":   "🎙 Голосовое",
}


def gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👨 Мужчина", callback_data=f"gender:{Gender.MALE.value}"),
        InlineKeyboardButton(text="👩 Женщина", callback_data=f"gender:{Gender.FEMALE.value}"),
        InlineKeyboardButton(text="🌈 Другое",  callback_data=f"gender:{Gender.OTHER.value}"),
    ]])


def seeking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Мужчин",  callback_data=f"seek:{SeekingGender.MALE.value}"),
        InlineKeyboardButton(text="Женщин",  callback_data=f"seek:{SeekingGender.FEMALE.value}"),
        InlineKeyboardButton(text="Неважно", callback_data=f"seek:{SeekingGender.ANY.value}"),
    ]])


def goal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"goal:{goal.value}")]
        for goal, label in GOAL_LABELS.items()
    ])


def interests_kb(selected: set[str]) -> InlineKeyboardMarkup:
    rows = []
    items = list(INTEREST_LABELS.items())
    for i in range(0, len(items), 2):
        row = []
        for code, label in items[i:i+2]:
            mark = "✅ " if code in selected else ""
            row.append(InlineKeyboardButton(text=f"{mark}{label}", callback_data=f"int:{code}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text=f"✅ Готово ({len(selected)}/10)", callback_data="interests_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Сохранить", callback_data="profile_confirm"),
        InlineKeyboardButton(text="✏️ Изменить",  callback_data="profile_edit"),
    ]])


def candidate_kb(uid: int, overlap_text: str = "") -> InlineKeyboardMarkup:
    hint = f" · {overlap_text}" if overlap_text else ""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"❤️ Лайк{hint}", callback_data=f"like:{uid}"),
        InlineKeyboardButton(text="➡️ Дальше",      callback_data=f"skip:{uid}"),
    ]])


def chat_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏳ Продлить чат",    callback_data=f"extend:{chat_id}")],
        [InlineKeyboardButton(text="🚨 Серьёзный сигнал", callback_data=f"danger:{chat_id}")],
    ])


def paid_catalog_kb(catalog: dict) -> InlineKeyboardMarkup:
    from app.core.enums import PaidFeature
    rows = [
        [InlineKeyboardButton(text=f"{p['title_ru']} · {p['stars']}⭐",
                              callback_data=f"buy:{feat.value}")]
        for feat, p in catalog.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
