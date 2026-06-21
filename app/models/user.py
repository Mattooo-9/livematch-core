from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.photo import Photo
    from app.models.verification import Verification

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import UserState
from app.models.mixins import IDMixin, TimestampMixin, utcnow


def generate_referral_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")[:8]


class User(IDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)

    state: Mapped[UserState] = mapped_column(
        SAEnum(UserState, native_enum=False, length=32), default=UserState.NEW, nullable=False, index=True
    )

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    spam_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    referral_code: Mapped[str] = mapped_column(
        String(16), unique=True, nullable=False, default=generate_referral_code, index=True
    )
    referred_by_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    device_fingerprint: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    last_active_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False, index=True)

    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    photos: Mapped[list["Photo"]] = relationship(
        "Photo", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    verification: Mapped[Optional["Verification"]] = relationship(
        "Verification", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.tg_id} state={self.state}>"


Index("ix_users_state_last_active", User.state, User.last_active_at)
