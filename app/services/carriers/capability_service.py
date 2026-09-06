import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Provider, ProviderCapability


class CarrierCapabilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, provider_id: uuid.UUID) -> ProviderCapability | None:
        result = await self.db.execute(
            select(ProviderCapability).where(ProviderCapability.provider_id == provider_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[dict]:
        result = await self.db.execute(
            select(Provider, ProviderCapability).outerjoin(
                ProviderCapability, Provider.id == ProviderCapability.provider_id
            )
        )
        rows = []
        for provider, caps in result.all():
            rows.append({
                "provider_id": str(provider.id),
                "provider": provider.name,
                "capabilities": {
                    "tracking": caps.tracking if caps else False,
                    "live_quote": caps.live_quote if caps else False,
                    "availability": caps.availability if caps else False,
                    "delivery_estimate": caps.delivery_estimate if caps else False,
                    "booking": caps.booking if caps else False,
                    "returns": caps.returns if caps else False,
                    "claims": caps.claims if caps else False,
                    "settlements": caps.settlements if caps else False,
                    "webhooks": caps.webhooks if caps else False,
                },
            })
        return rows
