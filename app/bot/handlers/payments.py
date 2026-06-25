from __future__ import annotations
from aiogram import F, Router
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from app.bot.keyboards.inline import paid_catalog_kb
from app.bot.keyboards.main_menu import BTN_PAY
from app.core.enums import PaidFeature, PaymentProviderName
from app.models.payment import Payment
from app.payments.catalog import FEATURE_CATALOG
from app.services import chat_service, payment_service

router = Router(name="payments")


@router.message(F.text.in_({"/pay", BTN_PAY}))
async def cmd_pay(message: Message, **kwargs):
    await message.answer(
        "⭐ Telegram Stars — честные покупки.\n\n"
        "Деньги не покупают приоритет в поиске.\n"
        "Деньги покупают удобство, лимиты, дополнительные сценарии.",
        reply_markup=paid_catalog_kb(FEATURE_CATALOG),
    )


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(call: CallbackQuery, session, user, **kwargs):
    feature = PaidFeature(call.data.split(":", 1)[1])
    p = FEATURE_CATALOG[feature]
    payment = await payment_service.create_pending_payment(
        session, user_id=user.id, feature=feature, provider=PaymentProviderName.TELEGRAM_STARS
    )
    await call.message.answer_invoice(
        title=p["title_ru"],
        description=p["title_ru"],
        payload=f"payment:{payment.id}",
        currency="XTR",
        prices=[LabeledPrice(label=p["title_ru"], amount=p["stars"])],
        provider_token="",
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery, **kwargs):
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session, user, **kwargs):
    try:
        pid = int(message.successful_payment.invoice_payload.split(":", 1)[1])
    except (IndexError, ValueError):
        await message.answer("Платёж получен, но не опознан. Напиши @support.")
        return
    payment = await session.get(Payment, pid)
    if not payment:
        await message.answer("Платёж получен, запись не найдена. Напиши @support.")
        return
    await payment_service.mark_success_and_activate(
        session, payment, external_id=message.successful_payment.telegram_payment_charge_id
    )
    if payment.feature == PaidFeature.EXTEND_CHAT:
        chat = await chat_service.get_active_chat(session, user.id)
        if chat:
            chat.user_a_wants_extend = True
            chat.user_b_wants_extend = True
            await chat_service.request_extend(session, chat, chat.user_a_id)
    await message.answer(f"✅ {FEATURE_CATALOG[payment.feature]['title_ru']} активировано.")
