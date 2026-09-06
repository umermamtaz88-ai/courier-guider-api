import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.workflow.financial_service import ClaimService, RefundService, ReturnService

router = APIRouter()


class ReturnCreate(BaseModel):
    reason: str | None = None
    return_charge: float | None = None
    currency: str | None = None


class RefundCreate(BaseModel):
    order_id: str | None = None
    refund_type: str = "customer_refund"
    requested_amount: float | None = None
    currency: str | None = None
    reason: str | None = None


class ClaimCreate(BaseModel):
    claim_type: str
    claimed_amount: float | None = None
    currency: str | None = None
    evidence: dict | None = None


@router.get("/{shipment_id}/return")
async def get_return(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await ReturnService(db).get(current.tenant_id, shipment_id)
    if record is None:
        return {"status": "not_found"}
    return {"id": str(record.id), "status": record.status, "reason": record.reason}


@router.post("/{shipment_id}/return")
async def create_return(
    shipment_id: uuid.UUID,
    data: ReturnCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await ReturnService(db).create(current.tenant_id, shipment_id, data.model_dump(), current.user.id)
    return {"id": str(record.id), "status": record.status}


@router.get("/{shipment_id}/refund")
async def get_refund(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await RefundService(db).get(current.tenant_id, shipment_id)
    if record is None:
        return {"status": "not_found"}
    return {"id": str(record.id), "status": record.status, "requested_amount": float(record.requested_amount) if record.requested_amount else None}


@router.post("/{shipment_id}/refund")
async def create_refund(
    shipment_id: uuid.UUID,
    data: RefundCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await RefundService(db).create(current.tenant_id, shipment_id, data.model_dump(), current.user.id)
    return {"id": str(record.id), "status": record.status}


@router.get("/{shipment_id}/claim")
async def get_claim(
    shipment_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await ClaimService(db).get(current.tenant_id, shipment_id)
    if record is None:
        return {"status": "not_found"}
    return {"id": str(record.id), "status": record.status, "claim_type": record.claim_type}


@router.post("/{shipment_id}/claim")
async def create_claim(
    shipment_id: uuid.UUID,
    data: ClaimCreate,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    record = await ClaimService(db).create(current.tenant_id, shipment_id, data.model_dump(), current.user.id)
    return {"id": str(record.id), "status": record.status}
