"""Inline keyboards for in-flow actions (like/skip, extend chat, gender pick, etc.)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.enums import Gender, Goal, SeekingGender


def candidate_actions_kb(target_user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❤️ Лайк", callback_data=f"like:{target_user_id}"),
                InlineKeyboardButton(text="➡️ Пропустить", callback_data=f"skip:{target_user_id}"),
            ]
        ]
    )


def chat_actions_kb(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Продлить чат на 24ч", callback_data=f"extend:{chat_id}")],
            [InlineKeyboardButton(text="🚨 Опасность / мошенничество", callback_data=f"danger:{chat_id}")],
        ]
    )


def gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мужчина", callback_data=f"gender:{Gender.MALE.value}"),
                InlineKeyboardButton(text="Женщина", callback_data=f"gender:{Gender.FEMALE.value}"),
                InlineKeyboardButton(text="Другое", callback_data=f"gender:{Gender.OTHER.value}"),
            ]
        ]
    )


def seeking_gender_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Мужчин", callback_data=f"seek:{SeekingGender.MALE.value}"),
                InlineKeyboardButton(text="Женщин", callback_data=f"seek:{SeekingGender.FEMALE.value}"),
                InlineKeyboardButton(text="Неважно", callback_data=f"seek:{SeekingGender.ANY.value}"),
            ]
        ]
    )


GOAL_LABELS_RU = {
    Goal.COMMUNICATION: "Общение",
    Goal.DATE: "Свидание",
    Goal.INTIMATE: "Секс",
    Goal.REGULAR: "Регулярное",
    Goal.FRIENDSHIP: "Дружба",
    Goal.INTERESTS: "Интересы",
    Goal.EVENTS: "События",
}


def goal_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f"goal:{goal.value}")]
        for goal, label in GOAL_LABELS_RU.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="✅ Готово", callback_data="profile_confirm")]]
    )


INTEREST_LABELS_RU = {
    "MUSIC": "🎵 Музыка", "SPORT": "🏃 Спорт", "WALKS": "🚶 Прогулки", "CINEMA": "🎬 Кино",
    "GAMES": "🎮 Игры", "DANCING": "💃 Танцы", "FOOD": "🍜 Еда", "BUSINESS": "💼 Бизнес",
    "IT": "💻 IT", "ART": "🎨 Искусство", "NIGHT_CITY": "🌃 Ночной город", "TRAVEL": "✈️ Путешествия",
    "ADULT_18": "🔞 18+ знакомства", "QUICK_MEETUPS": "⚡ Быстрые встречи", "VOICE_CHAT": "🎙 Голосовое общение",
}


def interests_kb(selected_codes: set[str]) -> InlineKeyboardMarkup:
    rows = []
    codes = list(INTEREST_LABELS_RU.keys())
    for i in range(0, len(codes), 2):
        row = []
        for code in codes[i : i + 2]:
            mark = "✅ " if code in selected_codes else ""
            row.append(InlineKeyboardButton(text=f"{mark}{INTEREST_LABELS_RU[code]}", callback_data=f"int:{code}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="interests_done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
