import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.shipments.shipment_service import ShipmentService


class ShipmentTools:
    def __init__(self, db: AsyncSession):
        self.service = ShipmentService(db)

    async def get_shipment(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> dict | None:
        shipment = await self.service.get(tenant_id, shipment_id)
        if not shipment:
            return None
        return {
            "id": str(shipment.id),
            "reference_code": shipment.reference_code,
            "status": shipment.status.value if hasattr(shipment.status, "value") else shipment.status,
            "origin": f"{shipment.origin_city}, {shipment.origin_country}",
            "destination": f"{shipment.destination_city}, {shipment.destination_country}",
            "weight": float(shipment.total_weight) if shipment.total_weight else None,
            "tracking_number": shipment.tracking_number,
            "provider_id": str(shipment.provider_id) if shipment.provider_id else None,
            "items": [
                {"description": i.description, "quantity": i.quantity, "category": i.category}
                for i in shipment.items
            ],
            "events": [
                {"type": e.event_type, "title": e.title, "time": e.event_time.isoformat()}
                for e in shipment.events[-5:]
            ],
        }
