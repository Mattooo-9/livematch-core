from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services import community_service

router = APIRouter(prefix="/community", tags=["community"])


@router.get("")
async def list_communities(session: AsyncSession = Depends(get_db)):
    communities = await community_service.list_communities(session)
    return [{"code": c.code, "category": c.category.value, "name_ru": c.name_ru, "description": c.description} for c in communities]
