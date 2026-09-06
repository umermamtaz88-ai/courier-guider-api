import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Claim, Refund, ReturnRecord, Settlement, ShipmentEvent
from app.utils.audit import write_audit

RETURN_TRANSITIONS = {
    "return_initiated": {"in_return_transit"},
    "in_return_transit": {"return_received"},
    "return_received": set(),
}

REFUND_TRANSITIONS = {
    "requested": {"under_review"},
    "under_review": {"approved", "rejected"},
    "approved": {"paid"},
    "rejected": set(),
    "paid": set(),
}

CLAIM_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"under_review"},
    "under_review": {"approved", "rejected"},
    "approved": {"paid"},
    "rejected": set(),
    "paid": set(),
}


def _validate_transition(current: str, new: str, allowed: dict[str, set[str]]) -> None:
    if new == current:
        return
    if new not in allowed.get(current, set()):
        raise ValueError(f"Invalid transition from {current} to {new}")


class ReturnService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> ReturnRecord | None:
        result = await self.db.execute(
            select(ReturnRecord).where(ReturnRecord.tenant_id == tenant_id, ReturnRecord.shipment_id == shipment_id)
        )
        return result.scalar_one_or_none()

    async def create(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> ReturnRecord:
        record = ReturnRecord(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            reason=data.get("reason"),
            status="return_initiated",
            return_charge=data.get("return_charge"),
            currency=data.get("currency"),
        )
        self.db.add(record)
        self._add_event(tenant_id, shipment_id, "RETURN_STARTED", "Return initiated")
        await self.db.flush()
        await write_audit(self.db, tenant_id=tenant_id, user_id=user_id, action="return_created", entity_type="return", entity_id=record.id)
        return record

    def _add_event(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, event_type: str, title: str) -> None:
        self.db.add(ShipmentEvent(tenant_id=tenant_id, shipment_id=shipment_id, event_type=event_type, source="system", title=title))


class RefundService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> Refund | None:
        result = await self.db.execute(
            select(Refund).where(Refund.tenant_id == tenant_id, Refund.shipment_id == shipment_id)
        )
        return result.scalars().first()

    async def create(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> Refund:
        refund = Refund(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            order_id=data.get("order_id"),
            refund_type=data.get("refund_type", "customer_refund"),
            requested_amount=data.get("requested_amount"),
            currency=data.get("currency"),
            reason=data.get("reason"),
            status="requested",
        )
        self.db.add(refund)
        self.db.add(ShipmentEvent(
            tenant_id=tenant_id, shipment_id=shipment_id, event_type="REFUND_REQUESTED",
            source="user", title="Refund requested",
        ))
        await self.db.flush()
        await write_audit(self.db, tenant_id=tenant_id, user_id=user_id, action="refund_created", entity_type="refund", entity_id=refund.id)
        return refund


class ClaimService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> Claim | None:
        result = await self.db.execute(
            select(Claim).where(Claim.tenant_id == tenant_id, Claim.shipment_id == shipment_id)
        )
        return result.scalars().first()

    async def create(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict, user_id: uuid.UUID) -> Claim:
        claim = Claim(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            claim_type=data["claim_type"],
            status="draft",
            claimed_amount=data.get("claimed_amount"),
            currency=data.get("currency"),
            evidence=data.get("evidence"),
        )
        self.db.add(claim)
        self.db.add(ShipmentEvent(
            tenant_id=tenant_id, shipment_id=shipment_id, event_type="CLAIM_OPENED",
            source="user", title="Claim opened",
        ))
        await self.db.flush()
        await write_audit(self.db, tenant_id=tenant_id, user_id=user_id, action="claim_created", entity_type="claim", entity_id=claim.id)
        return claim


class SettlementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_shipment(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID) -> list[Settlement]:
        result = await self.db.execute(
            select(Settlement).where(Settlement.tenant_id == tenant_id, Settlement.shipment_id == shipment_id)
        )
        return list(result.scalars().all())
