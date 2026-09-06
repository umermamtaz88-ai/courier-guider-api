import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Provider, ProviderService


class ServiceabilityService:
    async def check(
        self,
        db: AsyncSession,
        *,
        provider_id: uuid.UUID,
        origin_country: str,
        destination_country: str,
        origin_city: str | None = None,
        destination_city: str | None = None,
    ) -> dict:
        from datetime import UTC, datetime

        result = await db.execute(
            select(Provider).where(Provider.id == provider_id, Provider.active.is_(True))
        )
        provider = result.scalar_one_or_none()
        if provider is None:
            return {"serviceable": False, "source": "database", "reason": "provider_not_found"}

        svc_result = await db.execute(
            select(ProviderService).where(
                ProviderService.provider_id == provider_id,
                ProviderService.active.is_(True),
            )
        )
        services = list(svc_result.scalars().all())
        if not services:
            return {"serviceable": False, "source": "database", "reason": "no_active_services"}

        for svc in services:
            coverage = svc.coverage_json or {}
            origins = coverage.get("origins", [])
            destinations = coverage.get("destinations", [])
            if origins and origin_country not in origins and origin_city not in origins:
                continue
            if destinations and destination_country not in destinations and destination_city not in destinations:
                continue
            return {
                "provider": provider.name,
                "service": svc.name,
                "serviceable": True,
                "source": "provider_coverage",
                "checked_at": datetime.now(UTC).isoformat(),
            }

        return {
            "provider": provider.name,
            "serviceable": True,
            "source": "assumed_serviceable",
            "checked_at": datetime.now(UTC).isoformat(),
            "warning": "No explicit coverage data; verify with provider",
        }
