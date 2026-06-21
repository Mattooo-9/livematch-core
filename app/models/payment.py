from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import PaidFeature, PaymentProviderName, PaymentStatus
from app.models.mixins import IDMixin, TimestampMixin


class Payment(IDMixin, TimestampMixin, Base):
    __tablename__ = "payments"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProviderName] = mapped_column(
        SAEnum(PaymentProviderName, native_enum=False, length=32), nullable=False, index=True
    )
    feature: Mapped[PaidFeature] = mapped_column(
        SAEnum(PaidFeature, native_enum=False, length=32), nullable=False, index=True
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)  # cents / stars, integer to avoid float issues
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="XTR")  # XTR = Telegram Stars
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, native_enum=False, length=16), default=PaymentStatus.PENDING, nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    payload: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
