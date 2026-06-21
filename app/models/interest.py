from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.profile import Profile

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import InterestCategory
from app.models.mixins import IDMixin


class Interest(IDMixin, Base):
    """Static catalog of interests, seeded via migration."""

    __tablename__ = "interests"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category: Mapped[InterestCategory] = mapped_column(
        SAEnum(InterestCategory, native_enum=False, length=32), nullable=False, index=True
    )
    name_ru: Mapped[str] = mapped_column(String(64), nullable=False)
    name_en: Mapped[str] = mapped_column(String(64), nullable=False)


class UserInterest(Base):
    """Profile <-> Interest association (3-10 per profile, enforced in service layer)."""

    __tablename__ = "user_interests"

    profile_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    interest_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True
    )

    profile: Mapped["Profile"] = relationship("Profile", back_populates="interests")
    interest: Mapped["Interest"] = relationship("Interest", lazy="selectin")
