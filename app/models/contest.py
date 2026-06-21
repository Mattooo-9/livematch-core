from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import ContestType
from app.models.mixins import IDMixin, TimestampMixin


class Contest(IDMixin, TimestampMixin, Base):
    """Weekly mini-events. Voluntary, game-like, no public beauty rankings."""

    __tablename__ = "contests"

    type: Mapped[ContestType] = mapped_column(SAEnum(ContestType, native_enum=False, length=24), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    entries: Mapped[list["ContestEntry"]] = relationship(
        "ContestEntry", back_populates="contest", cascade="all, delete-orphan"
    )


class ContestEntry(IDMixin, TimestampMixin, Base):
    __tablename__ = "contest_entries"

    contest_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    payload: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    contest: Mapped["Contest"] = relationship("Contest", back_populates="entries")
