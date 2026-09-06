"""Courier Guider live tracking service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.carrier_tools import CarrierTools
from app.db.models import TrackingEvent
from app.services.shipments.shipment_service import ShipmentService


class TrackingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.shipments = ShipmentService(db)
        self.carrier_tools = CarrierTools(db)

    async def get_tracking(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> dict:
        shipment = await self.shipments.get(tenant_id, shipment_id)
        if shipment is None:
            return {"status": "not_found"}
        if not shipment.tracking_number or not shipment.provider_id:
            return {
                "status": "unavailable",
                "message": "Shipment has no tracking number or provider assigned",
            }
        result = await self.carrier_tools.get_tracking(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=shipment.provider_id,
            tracking_number=shipment.tracking_number,
        )
        await self._persist_event(shipment_id, shipment.provider_id, result)
        return result

    async def sync_tracking(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> dict:
        return await self.get_tracking(tenant_id, shipment_id)

    async def _persist_event(self, shipment_id: uuid.UUID, provider_id: uuid.UUID, payload: dict) -> None:
        if payload.get("status") in ("tool_unavailable", "capability_unavailable", "not_found"):
            return
        external_id = payload.get("external_reference") or payload.get("tracking_number")
        event = TrackingEvent(
            shipment_id=shipment_id,
            provider_id=provider_id,
            external_event_id=str(external_id) if external_id else None,
            status=payload.get("status_category", payload.get("status", "unknown")),
            event_time=payload.get("event_time") or datetime.now(UTC),
            location=payload.get("location"),
            description=payload.get("description"),
            raw_payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
