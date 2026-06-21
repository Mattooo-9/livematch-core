"""
Telegram Stars provider -- fully functional. Stars payments don't need a
classic webhook: aiogram receives PreCheckoutQuery + Message(successful_payment)
directly from Telegram, handled in app/bot/handlers/payments.py. This class
exists to keep the same PaymentProvider interface as fiat providers, and is
used for invoice-payload bookkeeping / catalog lookups.
"""
from __future__ import annotations

from app.payments.base import InvoiceRequest, InvoiceResult, PaymentProvider


class TelegramStarsProvider(PaymentProvider):
    name = "TELEGRAM_STARS"

    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        # Actual invoice sending happens via bot.send_invoice(...) in the bot
        # layer (needs the aiogram Bot instance) -- see services/payment_service.py.
        return InvoiceResult(success=True)

    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        # Not used -- Stars confirmations arrive as Telegram updates, not HTTP webhooks.
        return None
