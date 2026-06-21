from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.enums import ModerationSignalType, ModerationStatus
from app.models.mixins import IDMixin, TimestampMixin


class ModerationQueueItem(IDMixin, TimestampMixin, Base):
    """
    Serious-signal inbox. Danger-button reports and auto-detected risky dialogs
    land here for human review -- they never trigger an automatic ban.
    """

    __tablename__ = "moderation_queue"

    signal_type: Mapped[ModerationSignalType] = mapped_column(
        SAEnum(ModerationSignalType, native_enum=False, length=32), nullable=False, index=True
    )
    status: Mapped[ModerationStatus] = mapped_column(
        SAEnum(ModerationStatus, native_enum=False, length=16), default=ModerationStatus.OPEN, nullable=False, index=True
    )
    reporter_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True, index=True)
    chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("chats.id"), nullable=True)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("messages.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
