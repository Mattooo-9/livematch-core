"""LiqPay provider -- interface implemented, real API calls are TODO (UA market)."""
from __future__ import annotations

from app.core.config import settings
from app.payments.base import InvoiceRequest, InvoiceResult, PaymentProvider


class LiqPayProvider(PaymentProvider):
    name = "LIQPAY"

    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        if not (settings.LIQPAY_PUBLIC_KEY and settings.LIQPAY_PRIVATE_KEY):
            return InvoiceResult(success=False, error="liqpay_not_configured")
        # TODO(production): build base64 data+signature per LiqPay API docs and
        # return a checkout pay_url (https://www.liqpay.ua/api/3/checkout).
        return InvoiceResult(success=False, error="liqpay_integration_todo")

    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        # TODO(production): verify sha1(private_key + data + private_key) signature.
        return None
