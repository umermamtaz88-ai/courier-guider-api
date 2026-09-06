import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import CurrentUser, require_tenant
from app.services.workflow.cod_reconciliation_service import CodReconciliationService

router = APIRouter()


class CodReconcileRequest(BaseModel):
    order_expected: float | None = None
    shipment_cod_amount: float | None = None
    provider_collected: float | None = None
    provider_settled: float | None = None
    company_received: float | None = None
    currency: str = "PKR"


@router.post("/{shipment_id}/cod-reconcile")
async def reconcile_cod(
    shipment_id: uuid.UUID,
    data: CodReconcileRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    try:
        record = await CodReconciliationService(db).reconcile(
            current.tenant_id, shipment_id, data.model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "id": str(record.id),
        "status": record.status,
        "discrepancy": float(record.discrepancy) if record.discrepancy else 0,
        "discrepancy_type": record.discrepancy_type,
    }
