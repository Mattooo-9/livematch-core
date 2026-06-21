from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.interest import UserInterest

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import Gender, Goal, SeekingGender
from app.models.mixins import IDMixin, TimestampMixin, utcnow


class Profile(IDMixin, TimestampMixin, Base):
    """The intentionally SHORT questionnaire. Less text, more clarity."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    city: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    geo_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    geo_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[Gender] = mapped_column(SAEnum(Gender, native_enum=False, length=16), nullable=False)
    seeking_gender: Mapped[SeekingGender] = mapped_column(
        SAEnum(SeekingGender, native_enum=False, length=16), nullable=False
    )
    goal: Mapped[Goal] = mapped_column(SAEnum(Goal, native_enum=False, length=16), nullable=False, index=True)

    radius_km: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)

    activity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    behavior_rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)  # 0..10

    # incoming attention balancing -- reset every INCOMING_LIMIT_WINDOW_HOURS
    incoming_counter: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    incoming_counter_reset_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, nullable=False
    )

    last_dialog_at: Mapped[Optional[datetime]] = mapped_column(DateTime(), nullable=True)
    is_invisible_pause: Mapped[bool] = mapped_column(default=False, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="profile")
    interests: Mapped[list["UserInterest"]] = relationship(
        "UserInterest", back_populates="profile", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Profile user_id={self.user_id} city={self.city} goal={self.goal}>"


Index("ix_profiles_city_district_goal", Profile.city, Profile.district, Profile.goal)
