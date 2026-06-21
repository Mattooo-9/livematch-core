from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import ReferralStatus
from app.models.mixins import IDMixin, TimestampMixin


class Referral(IDMixin, TimestampMixin, Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("referred_id", name="uq_referral_referred_once"),)

    referrer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    referred_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[ReferralStatus] = mapped_column(
        SAEnum(ReferralStatus, native_enum=False, length=16), default=ReferralStatus.PENDING, nullable=False, index=True
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    antifraud_note: Mapped[Optional[str]] = mapped_column(nullable=True)
