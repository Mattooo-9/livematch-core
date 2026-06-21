from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """
    Naive UTC datetime, by convention. We deliberately avoid tz-aware columns:
    SQLite (used for fast unit tests) silently drops tzinfo on round-trip,
    which breaks Python-side arithmetic against Postgres-sourced aware values.
    Storing naive-but-always-UTC everywhere keeps both backends consistent.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# SQLite only auto-increments a primary key declared with INTEGER affinity
# (its ROWID-alias rule). BigInteger compiles to BIGINT there, which breaks
# autoincrement. Postgres/prod keeps real BigInteger; sqlite (tests) gets
# plain Integer -- functionally identical for our row counts.
_PK_TYPE = BigInteger().with_variant(Integer(), "sqlite")


class IDMixin:
    id: Mapped[int] = mapped_column(_PK_TYPE, primary_key=True, autoincrement=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), default=utcnow, onupdate=utcnow, nullable=False
    )
