"""
Pytest fixtures. Uses in-memory SQLite for speed/portability (CI doesn't need
a real Postgres). All app code avoids Postgres-only types, so this is a valid
functional proxy -- the migration itself is additionally verified manually
against real Postgres (see README).
"""
from __future__ import annotations


import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import Base
from app.models.interest import Interest


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    import app.core.redis_client as redis_client_module

    redis_client_module._fallback._store.clear()

    async with session_factory() as s:
        # seed the 15 interest categories every test needs
        codes = [
            "MUSIC", "SPORT", "WALKS", "CINEMA", "GAMES", "DANCING", "FOOD", "BUSINESS",
            "IT", "ART", "NIGHT_CITY", "TRAVEL", "ADULT_18", "QUICK_MEETUPS", "VOICE_CHAT",
        ]
        for code in codes:
            s.add(Interest(code=code, category=code, name_ru=code, name_en=code))
        await s.commit()
        yield s
