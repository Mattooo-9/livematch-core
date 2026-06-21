"""WayForPay provider -- interface implemented, real API calls are TODO (UA market)."""
from __future__ import annotations

from app.core.config import settings
from app.payments.base import InvoiceRequest, InvoiceResult, PaymentProvider


class WayForPayProvider(PaymentProvider):
    name = "WAYFORPAY"

    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        if not (settings.WAYFORPAY_MERCHANT_ACCOUNT and settings.WAYFORPAY_SECRET_KEY):
            return InvoiceResult(success=False, error="wayforpay_not_configured")
        # TODO(production): build the WayForPay PURCHASE form/request with HMAC-MD5 signature.
        return InvoiceResult(success=False, error="wayforpay_integration_todo")

    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        # TODO(production): verify WayForPay's signature scheme on the service-side callback.
        return None
