"""Shared FastAPI dependencies: DB session, admin-token auth."""
from __future__ import annotations

from typing import AsyncIterator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import async_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def require_admin_token(x_admin_token: str = Header(default="")) -> None:
    if not x_admin_token or x_admin_token != settings.ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_admin_token")
