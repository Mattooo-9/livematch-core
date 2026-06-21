from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IDMixin, TimestampMixin


class Like(IDMixin, TimestampMixin, Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="uq_like_pair"),)

    from_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
