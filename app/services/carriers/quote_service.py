import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.carrier_tools import CarrierTools
from app.integrations.carriers.base import QuoteRequest
from app.services.carriers.capability_service import CarrierCapabilityService


class QuoteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tools = CarrierTools(db)
        self.caps = CarrierCapabilityService(db)

    async def get_quote(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None,
        provider_id: uuid.UUID,
        request: QuoteRequest,
    ) -> dict:
        caps = await self.caps.get(provider_id)
        if caps and not caps.live_quote:
            return {"status": "capability_unavailable", "live_quote": False}
        return await self.tools.get_quote(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=provider_id,
            request=request,
        )
