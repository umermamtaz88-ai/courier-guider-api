import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Order
from app.db.session import get_db
from app.integrations.commerce.registry import CommerceRegistry
from app.security.auth import CurrentUser, require_tenant
from app.services.orders.order_service import OrderService
from app.utils.idempotency import get_idempotent_response, store_idempotent_response

router = APIRouter()


class OrderImportRequest(BaseModel):
    platform: str = "mock"
    external_order_id: str | None = None


@router.get("")
async def list_orders(
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.tenant_id == current.tenant_id).order_by(Order.created_at.desc()).limit(50)
    )
    return [
        {
            "id": str(o.id),
            "external_order_id": o.external_order_id,
            "platform": o.platform,
            "status": o.status.value,
            "total_amount": float(o.total_amount) if o.total_amount else None,
        }
        for o in result.scalars().all()
    ]


@router.post("/import")
async def import_order(
    data: OrderImportRequest,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if idempotency_key:
        cached = await get_idempotent_response(
            db, tenant_id=current.tenant_id, key=idempotency_key, operation="order_import"
        )
        if cached:
            return cached

    adapter = CommerceRegistry().get(data.platform)
    if adapter is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported platform")

    if data.external_order_id:
        commerce_order = await adapter.get_order(tenant_id=current.tenant_id, external_order_id=data.external_order_id)
        if commerce_order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found on platform")
        orders = [commerce_order]
    else:
        orders = await adapter.list_orders(tenant_id=current.tenant_id)

    service = OrderService(db)
    imported = []
    for order_data in orders:
        order = await service.import_order(current.tenant_id, order_data)
        imported.append({"id": str(order.id), "external_order_id": order.external_order_id})

    response = {"imported": imported, "count": len(imported)}
    if idempotency_key:
        await store_idempotent_response(
            db,
            tenant_id=current.tenant_id,
            key=idempotency_key,
            operation="order_import",
            response=response,
        )
    return response


@router.post("/{order_id}/convert-to-shipment")
async def convert_order_to_shipment(
    order_id: uuid.UUID,
    current: CurrentUser = Depends(require_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await OrderService(db).convert_to_shipment(current.tenant_id, order_id)
    if result.get("error"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result
