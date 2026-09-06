import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Claim,
    DeliveryException,
    Refund,
    ReturnRecord,
    Settlement,
    Shipment,
    ShipmentIssue,
    ShipmentStatus,
)


class ExceptionCenterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard(self, tenant_id: uuid.UUID) -> dict:
        delayed = await self.db.scalar(
            select(func.count()).select_from(Shipment).where(
                Shipment.tenant_id == tenant_id,
                Shipment.status == ShipmentStatus.IN_TRANSIT,
            )
        )
        ndr = await self.db.scalar(
            select(func.count()).select_from(DeliveryException).where(
                DeliveryException.tenant_id == tenant_id,
                DeliveryException.resolution_status.in_(["ndr_open", "customer_contacted"]),
            )
        )
        returns = await self.db.scalar(
            select(func.count()).select_from(ReturnRecord).where(ReturnRecord.tenant_id == tenant_id)
        )
        missing_docs = await self.db.scalar(
            select(func.count()).select_from(ShipmentIssue).where(
                ShipmentIssue.tenant_id == tenant_id,
                ShipmentIssue.issue_type == "missing_document",
                ShipmentIssue.status == "open",
            )
        )
        refunds_pending = await self.db.scalar(
            select(func.count()).select_from(Refund).where(
                Refund.tenant_id == tenant_id,
                Refund.status.in_(["requested", "under_review"]),
            )
        )
        claims_open = await self.db.scalar(
            select(func.count()).select_from(Claim).where(
                Claim.tenant_id == tenant_id,
                Claim.status.in_(["draft", "submitted", "under_review"]),
            )
        )
        settlements_overdue = await self.db.scalar(
            select(func.count()).select_from(Settlement).where(
                Settlement.tenant_id == tenant_id,
                Settlement.status == "pending",
            )
        )

        return {
            "delayed_shipments": delayed,
            "ndr_shipments": ndr,
            "returned_shipments": returns,
            "missing_documents": missing_docs,
            "refunds_pending": refunds_pending,
            "claims_open": claims_open,
            "settlements_overdue": settlements_overdue,
            "sla_breaches": 0,
            "provider_outages": 0,
        }
