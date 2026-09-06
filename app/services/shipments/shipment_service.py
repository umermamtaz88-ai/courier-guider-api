import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Document, Shipment, ShipmentDirection, ShipmentEvent, ShipmentIssue, ShipmentItem, ShipmentStatus, Task


class ShipmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, tenant_id: uuid.UUID, data: dict) -> Shipment:
        ref = data.get("reference_code") or f"SHP-{uuid.uuid4().hex[:8].upper()}"
        direction_raw = data.get("direction", "export")
        direction = ShipmentDirection(direction_raw) if isinstance(direction_raw, str) else direction_raw
        shipment = Shipment(
            tenant_id=tenant_id,
            reference_code=ref,
            direction=direction,
            service_type=data.get("service_type", "courier"),
            status=ShipmentStatus.DRAFT,
            origin_country=data.get("origin_country"),
            origin_city=data.get("origin_city"),
            destination_country=data.get("destination_country"),
            destination_city=data.get("destination_city"),
            total_weight=data.get("total_weight"),
            weight_unit=data.get("weight_unit", "kg"),
            declared_value=data.get("declared_value"),
            declared_currency=data.get("declared_currency"),
            cod_enabled=data.get("cod_enabled", False),
        )
        self.db.add(shipment)
        await self.db.flush()

        for item in data.get("items", []):
            self.db.add(
                ShipmentItem(
                    shipment_id=shipment.id,
                    description=item["description"],
                    category=item.get("category"),
                    quantity=item.get("quantity", 1),
                    weight=item.get("weight"),
                    hs_code=item.get("hs_code"),
                )
            )

        self.db.add(
            ShipmentEvent(
                tenant_id=tenant_id,
                shipment_id=shipment.id,
                event_type="SHIPMENT_CREATED",
                source="user",
                title="Shipment created",
                description=f"Reference {ref}",
            )
        )
        await self.db.flush()
        return shipment

    async def get(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> Shipment | None:
        result = await self.db.execute(
            select(Shipment)
            .options(selectinload(Shipment.items), selectinload(Shipment.events))
            .where(Shipment.id == shipment_id, Shipment.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_for_tenant(self, tenant_id: uuid.UUID, limit: int = 50) -> list[Shipment]:
        result = await self.db.execute(
            select(Shipment)
            .where(Shipment.tenant_id == tenant_id)
            .order_by(Shipment.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, shipment: Shipment, data: dict) -> Shipment:
        for field in (
            "origin_country", "origin_city", "destination_country", "destination_city",
            "total_weight", "declared_value", "declared_currency", "status", "provider_id",
            "service_id", "tracking_number",
        ):
            if field in data and data[field] is not None:
                setattr(shipment, field, data[field])
        await self.db.flush()
        return shipment

    async def add_event(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict) -> ShipmentEvent:
        event = ShipmentEvent(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            event_type=data["event_type"],
            source=data.get("source", "user"),
            title=data["title"],
            description=data.get("description"),
            data=data.get("data"),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def timeline(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[ShipmentEvent]:
        result = await self.db.execute(
            select(ShipmentEvent)
            .where(ShipmentEvent.tenant_id == tenant_id, ShipmentEvent.shipment_id == shipment_id)
            .order_by(ShipmentEvent.event_time.desc())
        )
        return list(result.scalars().all())

    async def health(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> dict:
        shipment = await self.get(tenant_id, shipment_id)
        if shipment is None:
            return {"status": "not_found"}
        docs = await self.db.execute(
            select(Document).where(Document.shipment_id == shipment_id, Document.tenant_id == tenant_id)
        )
        documents = list(docs.scalars().all())
        issues = await self.db.execute(
            select(ShipmentIssue).where(ShipmentIssue.shipment_id == shipment_id, ShipmentIssue.status == "open")
        )
        open_issues = list(issues.scalars().all())
        tasks = await self.db.execute(
            select(Task).where(Task.shipment_id == shipment_id, Task.status == "open")
        )
        pending_tasks = list(tasks.scalars().all())
        missing = max(0, 1 - len([d for d in documents if d.status == "processed"]))
        return {
            "status": "action_required" if open_issues or missing else "ok",
            "documents": {
                "complete": len([d for d in documents if d.status == "processed"]),
                "missing": missing,
                "conflicts": len([i for i in open_issues if i.issue_type == "mismatch"]),
            },
            "open_issues": len(open_issues),
            "pending_tasks": len(pending_tasks),
            "tracking": {"status": shipment.status.value if hasattr(shipment.status, "value") else shipment.status},
            "next_actions": [i.title for i in open_issues[:3]] or ["No immediate actions"],
        }
