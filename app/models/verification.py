from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import VerificationMethod, VerificationStatus
from app.models.mixins import IDMixin, TimestampMixin


class Verification(IDMixin, TimestampMixin, Base):
    __tablename__ = "verifications"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, native_enum=False, length=16),
        default=VerificationStatus.NONE,
        nullable=False,
        index=True,
    )
    method: Mapped[Optional[VerificationMethod]] = mapped_column(
        SAEnum(VerificationMethod, native_enum=False, length=24), nullable=True
    )
    gesture_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    submitted_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    reviewer_note: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="verification")
