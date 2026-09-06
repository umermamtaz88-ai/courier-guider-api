import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Provider, ProviderCapability
from app.integrations.carriers.base import CarrierAdapter
from app.integrations.carriers.mock import MockCarrierAdapter
from app.integrations.carriers.provider_a import TCSAdapter
from app.integrations.carriers.provider_b import LeopardsAdapter


class CarrierRegistry:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_adapter(self, provider_id: uuid.UUID) -> CarrierAdapter | None:
        result = await self.db.execute(select(Provider).where(Provider.id == provider_id))
        provider = result.scalar_one_or_none()
        if provider is None:
            return None
        if provider.slug == "tcs":
            return TCSAdapter(provider_id=provider.id)
        if provider.slug == "leopards":
            return LeopardsAdapter(provider_id=provider.id)
        return MockCarrierAdapter(provider_id=provider.id, provider_name=provider.name)

    async def get_capabilities(self, provider_id: uuid.UUID) -> ProviderCapability | None:
        result = await self.db.execute(
            select(ProviderCapability).where(ProviderCapability.provider_id == provider_id)
        )
        return result.scalar_one_or_none()
