"""Main reply keyboard -- short labels, no morализаторство, always clear next action."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.core.config import settings

BTN_CREATE_PROFILE = "📝 Создать анкету"
BTN_EDIT_PROFILE = "✏️ Изменить анкету"
BTN_SEARCH = "🔎 Искать"
BTN_PAUSE = "⏸ Пауза"
BTN_MY_INTERESTS = "🎯 Мои интересы"
BTN_COMMUNITY = "👥 Комьюнити"
BTN_EVENTS = "🎉 События"
BTN_REFERRAL = "🔗 Рефералка"
BTN_PAID = "⭐ Платные возможности"
BTN_STATUS = "📊 Статус сервиса"
BTN_OPEN_CHAT = "💬 Открыть чат"
BTN_WEBAPP = "🚀 Открыть приложение"


def main_menu(has_profile: bool) -> ReplyKeyboardMarkup:
    rows = []
    if not has_profile:
        rows.append([KeyboardButton(text=BTN_CREATE_PROFILE)])
    else:
        rows.append([KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_OPEN_CHAT)])
        rows.append([
            KeyboardButton(text=BTN_WEBAPP, web_app=WebAppInfo(url=settings.WEBAPP_BASE_URL)),
        ])
        rows.append([KeyboardButton(text=BTN_EDIT_PROFILE), KeyboardButton(text=BTN_MY_INTERESTS)])
        rows.append([KeyboardButton(text=BTN_COMMUNITY), KeyboardButton(text=BTN_EVENTS)])
        rows.append([KeyboardButton(text=BTN_REFERRAL), KeyboardButton(text=BTN_PAID)])
        rows.append([KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_PAUSE)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
