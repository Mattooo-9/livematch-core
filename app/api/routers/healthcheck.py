from fastapi import APIRouter
from sqlalchemy import text

from app.core.db import async_session_factory
from app.core.redis_client import safe_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def healthcheck():
    db_ok = True
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_client = await safe_redis()
    redis_ok = True
    try:
        await redis_client.ping()
    except Exception:
        redis_ok = False

    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "redis": redis_ok}
