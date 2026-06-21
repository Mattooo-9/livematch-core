from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services import contest_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(city: str | None = None, session: AsyncSession = Depends(get_db)):
    contests = await contest_service.list_active_contests(session, city=city)
    return [
        {"id": c.id, "type": c.type.value, "title": c.title, "description": c.description,
         "starts_at": c.starts_at.isoformat(), "ends_at": c.ends_at.isoformat(), "is_paid": c.is_paid}
        for c in contests
    ]
