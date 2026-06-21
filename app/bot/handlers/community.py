"""/community -- interest-based communities, not a noisy default chat."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.services import community_service

router = Router(name="community")


def _communities_kb(communities, joined_codes: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for c in communities:
        mark = "✅ " if c.code in joined_codes else "➕ "
        rows.append([InlineKeyboardButton(text=f"{mark}{c.name_ru}", callback_data=f"community:{c.code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_({"/community", "👥 Комьюнити"}))
async def cmd_community(message: Message, session, user, **kwargs):
    communities = await community_service.list_communities(session)
    mine = await community_service.my_communities(session, user.id)
    joined_codes = {c.code for c in mine}
    if not communities:
        await message.answer("Комьюнити пока не созданы (нужно засеять данные миграцией).")
        return
    await message.answer("Комьюнити по интересам:", reply_markup=_communities_kb(communities, joined_codes))


@router.callback_query(F.data.startswith("community:"))
async def cb_toggle_community(call: CallbackQuery, session, user, **kwargs):
    code = call.data.split(":", 1)[1]
    mine = await community_service.my_communities(session, user.id)
    if code in {c.code for c in mine}:
        await community_service.leave_community(session, user.id, code)
        await call.answer("Вышел из комьюнити")
    else:
        await community_service.join_community(session, user.id, code)
        await call.answer("Добавлено ✅")

    communities = await community_service.list_communities(session)
    mine = await community_service.my_communities(session, user.id)
    joined_codes = {c.code for c in mine}
    await call.message.edit_reply_markup(reply_markup=_communities_kb(communities, joined_codes))
