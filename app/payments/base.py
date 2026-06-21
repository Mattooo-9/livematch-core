"""Common interface every payment provider must implement."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.enums import PaidFeature


@dataclass
class InvoiceRequest:
    user_id: int
    feature: PaidFeature
    amount_minor: int
    currency: str
    description: str
    payload: str


@dataclass
class InvoiceResult:
    success: bool
    external_id: str | None = None
    pay_url: str | None = None  # for redirect-based providers (Stripe/LiqPay/etc.)
    raw: dict | None = None
    error: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_invoice(self, req: InvoiceRequest) -> InvoiceResult:
        ...

    @abstractmethod
    async def verify_webhook(self, headers: dict, body: bytes) -> dict | None:
        """Returns a normalized event dict if signature/payload is valid, else None."""
        ...
