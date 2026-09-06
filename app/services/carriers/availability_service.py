import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.carriers.base import AvailabilityRequest
from app.integrations.carriers.registry import CarrierRegistry
from app.services.carriers.capability_service import CarrierCapabilityService


class AvailabilityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = CarrierRegistry(db)
        self.caps = CarrierCapabilityService(db)

    async def check(self, request: AvailabilityRequest) -> dict:
        caps = await self.caps.get(request.provider_id)
        if caps and not caps.availability:
            return {"status": "capability_unavailable", "available": False}

        adapter = await self.registry.get_adapter(request.provider_id)
        if adapter is None:
            return {"status": "tool_unavailable"}

        try:
            result = await adapter.get_service_availability(request)
            return result.model_dump(mode="json")
        except Exception as exc:
            return {"status": "tool_unavailable", "message": str(exc)}
