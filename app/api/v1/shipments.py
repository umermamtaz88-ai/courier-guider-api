import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ShipmentCreate, ShipmentResponse
from app.security.auth import CurrentUser, require_tenant
from app.services.providers.recommendation_service import RecommendationService
from app.services.shipments.shipment_service import ShipmentService

router = APIRouter()


class ShipmentUpdate(BaseModel):
    origin_country: str | None = None
    origin_city: str | None = None
    destination_country: str | None = None
    destination_city: str | None = None
    total_weight: float | None = None
    declared_value: float | None = None
    declared_currency: str | None = None
    status: str | None = None
    tracking_number: str | None = None


class ShipmentEventCreate(BaseModel):
    event_type: str
    title: str
    description: str | None = None
    source: str = "user"
    data: dict | None = None


@router.post("", response_model=ShipmentResponse)
async def create_shipment(
    data: ShipmentCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    shipment = await service.create(current.tenant_id, data.model_dump())
    return shipment


@router.get("", response_model=list[ShipmentResponse])
async def list_shipments(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    return await service.list_for_tenant(current.tenant_id)


@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    shipment = await service.get(current.tenant_id, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return shipment


@router.patch("/{shipment_id}", response_model=ShipmentResponse)
async def update_shipment(
    shipment_id: uuid.UUID,
    data: ShipmentUpdate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    shipment = await service.get(current.tenant_id, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return await service.update(shipment, data.model_dump(exclude_none=True))


@router.post("/{shipment_id}/events")
async def add_event(
    shipment_id: uuid.UUID,
    data: ShipmentEventCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    event = await service.add_event(current.tenant_id, shipment_id, data.model_dump())
    return {"id": str(event.id), "event_type": event.event_type}


@router.get("/{shipment_id}/timeline")
async def shipment_timeline(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    events = await service.timeline(current.tenant_id, shipment_id)
    return [
        {"event_type": e.event_type, "title": e.title, "event_time": e.event_time.isoformat(), "source": e.source}
        for e in events
    ]


@router.get("/{shipment_id}/health")
async def shipment_health(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    return await service.health(current.tenant_id, shipment_id)


@router.get("/{shipment_id}/ai-summary")
async def shipment_ai_summary(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    from app.services.agent.agent_service import AgentService

    service = AgentService(db)
    return await service.chat(
        tenant_id=current.tenant_id,
        user_id=current.user.id,
        message="Summarize this shipment: current status, problems, next actions, and evidence.",
        shipment_id=shipment_id,
    )


@router.post("/plan")
async def plan_shipment(
    data: ShipmentCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    shipment_service = ShipmentService(db)
    rec_service = RecommendationService(db)
    shipment = await shipment_service.create(current.tenant_id, data.model_dump())

    recommendations = None
    if data.origin_country and data.destination_country and data.total_weight:
        recommendations = await rec_service.recommend(
            origin_country=data.origin_country,
            destination_country=data.destination_country,
            weight=data.total_weight,
        )

    missing = []
    if not data.origin_city:
        missing.append("origin_city")
    if not data.destination_city:
        missing.append("destination_city")
    if not data.declared_value:
        missing.append("declared_value")

    return {
        "shipment_id": str(shipment.id),
        "reference_code": shipment.reference_code,
        "status": shipment.status.value if hasattr(shipment.status, "value") else shipment.status,
        "missing": missing,
        "recommendations": recommendations,
    }


@router.post("/{shipment_id}/recommend-providers")
async def recommend_providers(
    shipment_id: uuid.UUID,
    priority: str = "balanced",
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = ShipmentService(db)
    shipment = await service.get(current.tenant_id, shipment_id)
    if shipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    if not all([shipment.origin_country, shipment.destination_country, shipment.total_weight]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shipment missing origin/destination/weight")

    rec = RecommendationService(db)
    return await rec.recommend(
        origin_country=shipment.origin_country,
        destination_country=shipment.destination_country,
        weight=float(shipment.total_weight),
        priority=priority,
        cod_required=shipment.cod_enabled,
    )


@router.post("/{shipment_id}/quote")
async def quote_shipment(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await recommend_providers(shipment_id, "cheapest", current, db)
