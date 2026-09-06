import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CodReconciliation, Shipment
from app.services.rules.quote_engine import reconcile_cod


class CodReconciliationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def reconcile(self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, data: dict) -> CodReconciliation:
        result = await self.db.execute(
            select(Shipment).where(Shipment.id == shipment_id, Shipment.tenant_id == tenant_id)
        )
        shipment = result.scalar_one_or_none()
        if shipment is None:
            raise ValueError("Shipment not found")

        calc = reconcile_cod(
            order_expected=Decimal(str(data["order_expected"])) if data.get("order_expected") else None,
            shipment_cod=Decimal(str(data.get("shipment_cod_amount", shipment.declared_value or 0))),
            provider_collected=Decimal(str(data["provider_collected"])) if data.get("provider_collected") else None,
            provider_settled=Decimal(str(data["provider_settled"])) if data.get("provider_settled") else None,
            company_received=Decimal(str(data["company_received"])) if data.get("company_received") else None,
        )

        record = CodReconciliation(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            order_expected=data.get("order_expected"),
            shipment_cod_amount=data.get("shipment_cod_amount"),
            provider_collected=data.get("provider_collected"),
            provider_settled=data.get("provider_settled"),
            company_received=data.get("company_received"),
            currency=data.get("currency", "PKR"),
            discrepancy=calc["total_discrepancy"],
            status=calc["status"],
            discrepancy_type=calc["discrepancies"][0]["type"] if calc["discrepancies"] else None,
        )
        self.db.add(record)
        await self.db.flush()
        return record
