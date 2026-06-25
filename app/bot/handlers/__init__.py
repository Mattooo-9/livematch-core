"""
Порядок регистрации роутеров ВАЖЕН.
chat.py регистрируется последним — его catch-all handler срабатывает только
если никакой другой хендлер (включая FSM-состояния) не обработал сообщение.
"""
from aiogram import Router
from app.bot.handlers import (
    admin, chat, community, events, payments, profile, referral, search, start, verify,
)


def build_root_router() -> Router:
    root = Router(name="root")
    # FSM-хендлеры (profile/verify) — сначала, чтобы FSM-состояния были приоритетны
    for r in (start.router, profile.router, verify.router,
              search.router, referral.router, payments.router,
              community.router, events.router, admin.router,
              chat.router):  # chat.router — ПОСЛЕДНИЙ (catch-all relay)
        root.include_router(r)
    return root
