"""
Async DB engine + session factory.
Works with postgresql+asyncpg:// in prod/docker and sqlite+aiosqlite:// in tests.
"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(url, echo=False, future=True, connect_args=connect_args)


engine = _make_engine(settings.DATABASE_URL)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency / general use async generator."""
    async with async_session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Use in bot handlers / background tasks where DI isn't available."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models():
    """Used only by tests (sqlite) to create tables without alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
