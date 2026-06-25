"""
Клавиатура главного меню. Всё в одном месте — никаких строк в нескольких файлах.
Константы с префиксом BTN_ — единственный источник правды для текстов кнопок.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from app.core.config import settings

# ── Тексты кнопок (единственный источник правды) ─────────────────────────────
BTN_CREATE  = "📝 Создать анкету"
BTN_EDIT    = "✏️ Изменить анкету"
BTN_SEARCH  = "🔎 Найти"
BTN_CHAT    = "💬 Мой чат"
BTN_STATUS  = "📡 Пульс"
BTN_PAUSE   = "⏸ Пауза"
BTN_RESUME  = "▶️ Продолжить поиск"
BTN_REF     = "🔗 Пригласить"
BTN_PAY     = "⭐ Возможности"
BTN_COMM    = "👥 Комьюнити"
BTN_EVENTS  = "🎉 События"
BTN_APP     = "🚀 Открыть приложение"

ALL_MENU_BUTTONS = {
    BTN_CREATE, BTN_EDIT, BTN_SEARCH, BTN_CHAT, BTN_STATUS,
    BTN_PAUSE, BTN_RESUME, BTN_REF, BTN_PAY, BTN_COMM, BTN_EVENTS, BTN_APP,
}


def main_menu(has_profile: bool, is_paused: bool = False) -> ReplyKeyboardMarkup:
    if not has_profile:
        rows = [[KeyboardButton(text=BTN_CREATE)]]
    else:
        pause_btn = BTN_RESUME if is_paused else BTN_PAUSE
        rows = [
            [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_CHAT)],
            [KeyboardButton(text=BTN_APP, web_app=WebAppInfo(url=settings.WEBAPP_BASE_URL))],
            [KeyboardButton(text=BTN_EDIT), KeyboardButton(text=BTN_COMM)],
            [KeyboardButton(text=BTN_EVENTS), KeyboardButton(text=BTN_REF)],
            [KeyboardButton(text=BTN_PAY), KeyboardButton(text=BTN_STATUS), KeyboardButton(text=pause_btn)],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)
