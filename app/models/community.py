from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import InterestCategory
from app.models.mixins import IDMixin, TimestampMixin


class Community(IDMixin, TimestampMixin, Base):
    """Interest-based community. NOT a generic noisy chat by default."""

    __tablename__ = "communities"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    category: Mapped[InterestCategory] = mapped_column(
        SAEnum(InterestCategory, native_enum=False, length=32), nullable=False, index=True
    )
    name_ru: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(512), default="", nullable=False)

    members: Mapped[list["CommunityMember"]] = relationship(
        "CommunityMember", back_populates="community", cascade="all, delete-orphan"
    )


class CommunityMember(Base):
    __tablename__ = "community_members"

    community_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    community: Mapped["Community"] = relationship("Community", back_populates="members")
