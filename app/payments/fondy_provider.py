"""Fondy provider -- interface implemented, real API calls are TODO (UA/EU market)."""
from __future__ import annotations

from app.core.config import settings
from app.payments.base import InvoiceRequest, InvoiceResult, PaymentProvider


class FondyProvider(PaymentProvider):
    name = "FONDY"

    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        if not (settings.FONDY_MERCHANT_ID and settings.FONDY_SECRET_KEY):
            return InvoiceResult(success=False, error="fondy_not_configured")
        # TODO(production): POST to https://api.fondy.eu/api/checkout/url/ with
        # merchant_id/order_id/amount/signature, return checkout_url as pay_url.
        return InvoiceResult(success=False, error="fondy_integration_todo")

    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        # TODO(production): verify Fondy's sha1 signature scheme.
        return None
