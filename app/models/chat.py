from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.match import Match
    from app.models.message import Message

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import ChatStatus
from app.models.mixins import IDMixin, TimestampMixin


class Chat(IDMixin, TimestampMixin, Base):
    __tablename__ = "chats"

    match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), unique=True)
    user_a_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_b_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    status: Mapped[ChatStatus] = mapped_column(
        SAEnum(ChatStatus, native_enum=False, length=16), default=ChatStatus.BUFFER, nullable=False, index=True
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True, index=True)
    extended_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user_a_wants_extend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_b_wants_extend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True, index=True)
    closed_reason: Mapped[Optional[str]] = mapped_column(nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="chat")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    def other_user(self, user_id: int) -> int:
        return self.user_b_id if user_id == self.user_a_id else self.user_a_id
