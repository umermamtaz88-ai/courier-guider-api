import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeliveryException, ShipmentEvent
from app.utils.audit import write_audit

NDR_TRANSITIONS = {
    "ndr_open": {"customer_contacted", "rescheduled", "return_initiated"},
    "customer_contacted": {"rescheduled", "return_initiated", "no_resolution"},
    "rescheduled": {"ndr_open"},
    "no_resolution": {"return_initiated"},
    "return_initiated": set(),
}


class NdrService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID,
        data: dict,
        user_id: uuid.UUID,
    ) -> DeliveryException:
        exc = DeliveryException(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=data.get("provider_id"),
            reason_code=data["reason_code"],
            reason_text=data.get("reason_text"),
            attempt_number=data.get("attempt_number", 1),
            resolution_status="ndr_open",
        )
        self.db.add(exc)
        self.db.add(ShipmentEvent(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            event_type="DELIVERY_FAILED",
            source="system",
            title="NDR opened",
            description=data.get("reason_text"),
        ))
        await self.db.flush()
        await write_audit(self.db, tenant_id=tenant_id, user_id=user_id, action="ndr_created", entity_type="delivery_exception", entity_id=exc.id)
        return exc

    async def update_status(
        self, tenant_id: uuid.UUID, exception_id: uuid.UUID, new_status: str, user_id: uuid.UUID
    ) -> DeliveryException | None:
        result = await self.db.execute(
            select(DeliveryException).where(DeliveryException.id == exception_id, DeliveryException.tenant_id == tenant_id)
        )
        exc = result.scalar_one_or_none()
        if exc is None:
            return None
        allowed = NDR_TRANSITIONS.get(exc.resolution_status, set())
        if new_status != exc.resolution_status and new_status not in allowed:
            raise ValueError(f"Invalid NDR transition: {exc.resolution_status} -> {new_status}")
        exc.resolution_status = new_status
        await self.db.flush()
        return exc

    async def list_for_shipment(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[DeliveryException]:
        result = await self.db.execute(
            select(DeliveryException).where(
                DeliveryException.tenant_id == tenant_id,
                DeliveryException.shipment_id == shipment_id,
            )
        )
        return list(result.scalars().all())
