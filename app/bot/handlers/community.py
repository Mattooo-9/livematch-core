from __future__ import annotations
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from app.bot.keyboards.main_menu import BTN_COMM
from app.services import community_service

router = Router(name="community")


def _kb(communities, joined: set[str]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=("✅ " if c.code in joined else "➕ ") + c.name_ru,
            callback_data=f"comm:{c.code}"
        )]
        for c in communities
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_({"/community", BTN_COMM}))
async def cmd_community(message: Message, session, user, **kwargs):
    communities = await community_service.list_communities(session)
    if not communities:
        await message.answer("Комьюнити скоро появятся.")
        return
    mine = await community_service.my_communities(session, user.id)
    await message.answer(
        "👥 Комьюнити по интересам.\n\nНе чаты — место чтобы находить людей со схожими увлечениями.",
        reply_markup=_kb(communities, {c.code for c in mine}),
    )


@router.callback_query(F.data.startswith("comm:"))
async def cb_community(call: CallbackQuery, session, user, **kwargs):
    code = call.data.split(":", 1)[1]
    mine = await community_service.my_communities(session, user.id)
    if code in {c.code for c in mine}:
        await community_service.leave_community(session, user.id, code)
        await call.answer("Вышел")
    else:
        await community_service.join_community(session, user.id, code)
        await call.answer("Добавлен ✅")
    communities = await community_service.list_communities(session)
    mine = await community_service.my_communities(session, user.id)
    await call.message.edit_reply_markup(reply_markup=_kb(communities, {c.code for c in mine}))
