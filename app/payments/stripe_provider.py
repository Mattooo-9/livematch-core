"""
Stripe provider -- interface implemented, real API calls are TODO.
To go live: `pip install stripe`, set STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET,
create a Checkout Session in create_invoice(), verify signature in verify_webhook()
using stripe.Webhook.construct_event().
"""
from __future__ import annotations

from app.core.config import settings
from app.payments.base import InvoiceRequest, InvoiceResult, PaymentProvider


class StripeProvider(PaymentProvider):
    name = "STRIPE"

    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        if not settings.STRIPE_SECRET_KEY:
            return InvoiceResult(success=False, error="stripe_not_configured")
        # TODO(production): create a real Stripe Checkout Session here, e.g.
        #   import stripe; stripe.api_key = settings.STRIPE_SECRET_KEY
        #   session = stripe.checkout.Session.create(...)
        #   return InvoiceResult(success=True, external_id=session.id, pay_url=session.url)
        return InvoiceResult(success=False, error="stripe_integration_todo")

    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        if not settings.STRIPE_WEBHOOK_SECRET:
            return None
        # TODO(production): verify with stripe.Webhook.construct_event(body, headers["stripe-signature"], secret)
        return None
