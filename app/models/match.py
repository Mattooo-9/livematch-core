from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.chat import Chat

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import MatchStatus
from app.models.mixins import IDMixin, TimestampMixin


class Match(IDMixin, TimestampMixin, Base):
    __tablename__ = "matches"

    user_a_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_b_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[MatchStatus] = mapped_column(
        SAEnum(MatchStatus, native_enum=False, length=16), default=MatchStatus.BUFFER, nullable=False, index=True
    )

    chat: Mapped["Chat"] = relationship("Chat", back_populates="match", uselist=False, cascade="all, delete-orphan")


Index("ix_matches_users", Match.user_a_id, Match.user_b_id)
