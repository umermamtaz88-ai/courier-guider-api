import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import LiveDataSnapshot, ProviderCapability
from app.integrations.carriers.base import QuoteRequest
from app.integrations.carriers.registry import CarrierRegistry


class CarrierTools:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = CarrierRegistry(db)
        self.settings = get_settings()

    async def get_tracking(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID,
        provider_id: uuid.UUID,
        tracking_number: str,
    ) -> dict:
        cached = await self._get_cached(tenant_id, shipment_id, provider_id, "tracking")
        if cached:
            return cached

        caps = await self.registry.get_capabilities(provider_id)
        if caps and not caps.tracking:
            return {"status": "capability_unavailable", "tracking": False}

        adapter = await self.registry.get_adapter(provider_id)
        if adapter is None:
            return {"status": "tool_unavailable", "message": "No carrier adapter configured"}

        try:
            result = await adapter.get_tracking(tracking_number)
            payload = result.model_dump(mode="json")
            await self._store_snapshot(
                tenant_id=tenant_id,
                shipment_id=shipment_id,
                provider_id=provider_id,
                data_type="tracking",
                payload=payload,
                source=result.source,
                event_time=result.event_time,
            )
            return payload
        except Exception as exc:
            stale = await self._get_cached(tenant_id, shipment_id, provider_id, "tracking", allow_stale=True)
            if stale:
                stale["status_note"] = "stale_cache_used"
                return stale
            return {"status": "tool_unavailable", "message": str(exc)}

    async def get_quote(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None,
        provider_id: uuid.UUID,
        request: QuoteRequest,
    ) -> dict:
        caps = await self.registry.get_capabilities(provider_id)
        if caps and not caps.live_quote:
            return {"status": "capability_unavailable", "live_quote": False}

        adapter = await self.registry.get_adapter(provider_id)
        if adapter is None:
            return {"status": "tool_unavailable"}

        try:
            result = await adapter.get_quote(request)
            payload = result.model_dump(mode="json")
            if shipment_id:
                await self._store_snapshot(
                    tenant_id=tenant_id,
                    shipment_id=shipment_id,
                    provider_id=provider_id,
                    data_type="quote",
                    payload=payload,
                    source=result.source.value if hasattr(result.source, "value") else str(result.source),
                    event_time=result.quoted_at,
                    max_age_seconds=self.settings.quote_max_age_seconds,
                )
            return payload
        except Exception as exc:
            return {"status": "tool_unavailable", "message": str(exc)}

    async def _get_cached(
        self,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID,
        provider_id: uuid.UUID,
        data_type: str,
        allow_stale: bool = False,
    ) -> dict | None:
        result = await self.db.execute(
            select(LiveDataSnapshot)
            .where(
                LiveDataSnapshot.tenant_id == tenant_id,
                LiveDataSnapshot.shipment_id == shipment_id,
                LiveDataSnapshot.provider_id == provider_id,
                LiveDataSnapshot.data_type == data_type,
            )
            .order_by(LiveDataSnapshot.retrieved_at.desc())
            .limit(1)
        )
        snap = result.scalar_one_or_none()
        if snap is None:
            return None
        now = datetime.now(UTC)
        fresh = snap.expires_at and snap.expires_at > now
        if fresh or allow_stale:
            payload = dict(snap.payload)
            payload["retrieved_at"] = snap.retrieved_at.isoformat()
            payload["stale"] = not fresh
            return payload
        return None

    async def _store_snapshot(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID,
        provider_id: uuid.UUID,
        data_type: str,
        payload: dict,
        source: str,
        event_time: datetime | None,
        max_age_seconds: int | None = None,
    ) -> None:
        now = datetime.now(UTC)
        max_age = max_age_seconds or self.settings.realtime_data_max_age_seconds
        snap = LiveDataSnapshot(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=provider_id,
            data_type=data_type,
            payload=payload,
            source=source,
            retrieved_at=now,
            event_time=event_time,
            expires_at=now + timedelta(seconds=max_age),
        )
        self.db.add(snap)
        await self.db.flush()
