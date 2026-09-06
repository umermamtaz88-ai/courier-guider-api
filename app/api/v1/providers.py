from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Provider
from app.db.session import get_db
from app.services.providers.recommendation_service import RecommendationService
from pydantic import BaseModel

router = APIRouter()


class CompareRequest(BaseModel):
    origin_country: str
    destination_country: str
    weight: float
    priority: str = "balanced"
    cod_required: bool = False


@router.get("")
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Provider).where(Provider.active.is_(True)))
    providers = list(result.scalars().all())
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "country": p.country,
            "provider_type": p.provider_type,
        }
        for p in providers
    ]


@router.get("/{provider_id}")
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    import uuid

    result = await db.execute(
        select(Provider)
        .options(selectinload(Provider.services), selectinload(Provider.policies))
        .where(Provider.id == uuid.UUID(provider_id))
    )
    provider = result.scalar_one()
    return {
        "id": str(provider.id),
        "name": provider.name,
        "slug": provider.slug,
        "services": [
            {"id": str(s.id), "name": s.name, "cod_supported": s.cod_supported}
            for s in provider.services
        ],
        "policies": [
            {"id": str(p.id), "policy_type": p.policy_type, "title": p.title}
            for p in provider.policies
        ],
    }


@router.get("/{provider_id}/services")
async def get_provider_services(provider_id: str, db: AsyncSession = Depends(get_db)):
    import uuid

    result = await db.execute(
        select(Provider).options(selectinload(Provider.services)).where(Provider.id == uuid.UUID(provider_id))
    )
    provider = result.scalar_one()
    return [{"id": str(s.id), "name": s.name, "cod_supported": s.cod_supported} for s in provider.services]


@router.get("/{provider_id}/policies")
async def get_provider_policies(provider_id: str, db: AsyncSession = Depends(get_db)):
    import uuid

    result = await db.execute(
        select(Provider).options(selectinload(Provider.policies)).where(Provider.id == uuid.UUID(provider_id))
    )
    provider = result.scalar_one()
    return [{"id": str(p.id), "policy_type": p.policy_type, "title": p.title} for p in provider.policies]


@router.post("/compare")
async def compare_providers(data: CompareRequest, db: AsyncSession = Depends(get_db)):
    service = RecommendationService(db)
    return await service.recommend(
        origin_country=data.origin_country,
        destination_country=data.destination_country,
        weight=data.weight,
        priority=data.priority,
        cod_required=data.cod_required,
    )
