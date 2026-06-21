from __future__ import annotations

from datetime import date as date_type
from typing import Optional

from sqlalchemy import BigInteger, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import IDMixin, TimestampMixin


class EventLog(IDMixin, TimestampMixin, Base):
    """Generic append-only event log, feeds metrics/AI insights."""

    __tablename__ = "event_logs"

    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)


class ActivityScore(IDMixin, TimestampMixin, Base):
    """Historical snapshots of a user's activity score (for trend analysis)."""

    __tablename__ = "activity_scores"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")  # daily / weekly


class SystemMetric(IDMixin, TimestampMixin, Base):
    __tablename__ = "system_metrics"

    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    dimension: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # e.g. city name, optional slice


class AIInsight(IDMixin, TimestampMixin, Base):
    __tablename__ = "ai_insights"

    report_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(String(4096), nullable=False)
    details_json: Mapped[Optional[str]] = mapped_column(String(8192), nullable=True)
