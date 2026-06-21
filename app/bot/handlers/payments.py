"""
/pay -- catalog + Telegram Stars checkout (XTR, no provider token required).
Fiat providers (Stripe/LiqPay/Fondy/WayForPay) are wired through PaymentService
but require real API keys to actually redirect -- see app/payments/*_provider.py.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery, LabeledPrice, Message, PreCheckoutQuery,
)
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.enums import PaidFeature, PaymentProviderName
from app.models.payment import Payment
from app.payments.catalog import FEATURE_CATALOG
from app.services import chat_service, payment_service

router = Router(name="payments")


def _catalog_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{p['title_ru']} -- {p['stars']} ⭐", callback_data=f"buy:{feature.value}")]
        for feature, p in FEATURE_CATALOG.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text.in_({"/pay", "⭐ Платные возможности"}))
async def cmd_pay(message: Message, **kwargs):
    await message.answer(
        "Платные возможности (Telegram Stars). Деньги не покупают приоритет привлекательности -- "
        "только удобство и расширенные лимиты.",
        reply_markup=_catalog_kb(),
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery, session, user, **kwargs):
    feature = PaidFeature(call.data.split(":", 1)[1])
    pricing = FEATURE_CATALOG[feature]

    payment = await payment_service.create_pending_payment(
        session, user_id=user.id, feature=feature, provider=PaymentProviderName.TELEGRAM_STARS
    )
    await call.message.answer_invoice(
        title=pricing["title_ru"],
        description=f"LiveMatch Core -- {pricing['title_ru']}",
        payload=f"payment:{payment.id}",
        currency="XTR",
        prices=[LabeledPrice(label=pricing["title_ru"], amount=pricing["stars"])],
        provider_token="",  # empty for Telegram Stars
    )
    await call.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery, **kwargs):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, session, user, **kwargs):
    payload = message.successful_payment.invoice_payload  # "payment:<id>"
    try:
        payment_id = int(payload.split(":", 1)[1])
    except (IndexError, ValueError):
        await message.answer("Платёж получен, но не удалось его сопоставить. Напиши в поддержку.")
        return

    payment = await session.get(Payment, payment_id)
    if payment is None:
        await message.answer("Платёж получен, но запись не найдена. Напиши в поддержку.")
        return

    await payment_service.mark_success_and_activate(
        session, payment, external_id=message.successful_payment.telegram_payment_charge_id
    )

    # contextual effects for features that need an active chat in hand
    if payment.feature == PaidFeature.EXTEND_CHAT:
        chat = await chat_service.get_active_chat(session, user.id)
        if chat:
            chat.user_a_wants_extend = True
            chat.user_b_wants_extend = True
            await chat_service.request_extend(session, chat, chat.user_a_id)

    await message.answer(f"Оплата прошла ✅ {FEATURE_CATALOG[payment.feature]['title_ru']} активировано.")
