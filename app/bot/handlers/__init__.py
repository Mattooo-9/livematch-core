from aiogram import Router

from app.bot.handlers import (
    start, profile, verify, search, referral, payments, community, events, admin, chat,
)


def build_root_router() -> Router:
    root = Router(name="root")
    # Order matters: chat.py has a broad catch-all text handler and must be LAST.
    for module_router in (
        start.router, profile.router, verify.router, search.router, referral.router,
        payments.router, community.router, events.router, admin.router, chat.router,
    ):
        root.include_router(module_router)
    return root
