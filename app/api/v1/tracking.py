import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.tracking.tracking_service import TrackingService

router = APIRouter()


@router.get("/{shipment_id}/tracking")
async def get_shipment_tracking(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TrackingService(db)
    result = await service.get_tracking(current.tenant_id, shipment_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    return result


@router.post("/{shipment_id}/tracking/sync")
async def sync_shipment_tracking(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    service = TrackingService(db)
    return await service.sync_tracking(current.tenant_id, shipment_id)
