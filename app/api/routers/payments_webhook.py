"""
Generic fiat-provider webhook entrypoint. Real signature verification + event
parsing is implemented per-provider in app/payments/*_provider.py (currently
TODO stubs for Stripe/LiqPay/Fondy/WayForPay -- Telegram Stars doesn't use this,
it confirms payments through bot updates instead, see app/bot/handlers/payments.py).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.db import async_session_factory
from app.core.enums import PaymentProviderName
from app.models.payment import Payment
from app.services import payment_service
from sqlalchemy import select

router = APIRouter(tags=["payments"])


@router.post("/webhook/payments/{provider}")
async def payments_webhook(provider: str, request: Request):
    try:
        provider_enum = PaymentProviderName(provider.upper())
    except ValueError:
        raise HTTPException(status_code=404, detail="unknown_provider")

    body = await request.body()
    handler = payment_service.get_provider(provider_enum)
    event = await handler.verify_webhook(dict(request.headers), body)
    if event is None:
        raise HTTPException(status_code=400, detail="invalid_or_unconfigured_webhook")

    async with async_session_factory() as session:
        res = await session.execute(select(Payment).where(Payment.external_id == event.get("payment_id")))
        payment = res.scalar_one_or_none()
        if payment is None:
            raise HTTPException(status_code=404, detail="payment_not_found")
        await payment_service.mark_success_and_activate(session, payment, external_id=event.get("payment_id"))
        await session.commit()

    return {"ok": True}
