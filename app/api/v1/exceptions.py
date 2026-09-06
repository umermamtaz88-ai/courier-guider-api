import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.exceptions.exception_center_service import ExceptionCenterService
from app.services.workflow.ndr_service import NdrService

router = APIRouter()
ndr_router = APIRouter()


class NdrCreate(BaseModel):
    reason_code: str
    reason_text: str | None = None
    attempt_number: int = 1
    provider_id: uuid.UUID | None = None


class NdrUpdate(BaseModel):
    resolution_status: str


@router.get("/dashboard")
async def exception_dashboard(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await ExceptionCenterService(db).get_dashboard(current.tenant_id)


@ndr_router.get("/shipments/{shipment_id}/ndr")
async def list_ndr(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    records = await NdrService(db).list_for_shipment(current.tenant_id, shipment_id)
    return [
        {
            "id": str(r.id),
            "reason_code": r.reason_code,
            "resolution_status": r.resolution_status,
            "attempt_number": r.attempt_number,
        }
        for r in records
    ]


@ndr_router.post("/shipments/{shipment_id}/ndr")
async def create_ndr(
    shipment_id: uuid.UUID,
    data: NdrCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await NdrService(db).create(
        current.tenant_id, shipment_id, data.model_dump(), current.user.id
    )
    return {"id": str(record.id), "resolution_status": record.resolution_status}


@ndr_router.patch("/ndr/{exception_id}")
async def update_ndr(
    exception_id: uuid.UUID,
    data: NdrUpdate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await NdrService(db).update_status(
            current.tenant_id, exception_id, data.resolution_status, current.user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NDR not found")
    return {"id": str(record.id), "resolution_status": record.resolution_status}
