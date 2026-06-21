from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import BigInteger, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import IDMixin, TimestampMixin


class Photo(IDMixin, TimestampMixin, Base):
    __tablename__ = "photos"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    telegram_file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    phash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # perceptual hash, hex string
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_flagged_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="photos")
