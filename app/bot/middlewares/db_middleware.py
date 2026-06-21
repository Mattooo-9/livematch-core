"""
Injects an AsyncSession + the current User (get-or-create) into every update's
handler kwargs, commits on success / rolls back on error, and touches presence.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from app.core.db import async_session_factory
from app.services import online_service, user_service


def _extract_user_event(event: TelegramObject):
    if isinstance(event, Update):
        if event.message:
            return event.message.from_user, event.message
        if event.callback_query:
            return event.callback_query.from_user, event.callback_query
        if event.pre_checkout_query:
            return event.pre_checkout_query.from_user, event.pre_checkout_query
    tg_user = getattr(event, "from_user", None)
    return tg_user, event


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            tg_user, _ = _extract_user_event(event)

            if tg_user is not None and not tg_user.is_bot:
                from app.core.config import settings

                user, created = await user_service.get_or_create_user(
                    session,
                    tg_id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name,
                    is_admin=tg_user.id in settings.admin_ids,
                )
                data["user"] = user
                data["user_created"] = created
            else:
                data["user"] = None
                data["user_created"] = False

            try:
                result = await handler(event, data)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

            if data.get("user") is not None:
                await online_service.mark_online(data["user"].id)

            return result
