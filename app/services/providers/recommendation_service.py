import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Provider, ProviderRate, ProviderService


class RecommendationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def recommend(
        self,
        *,
        origin_country: str,
        destination_country: str,
        weight: float,
        priority: str = "balanced",
        cod_required: bool = False,
    ) -> dict:
        result = await self.db.execute(
            select(Provider)
            .options(selectinload(Provider.services))
            .where(Provider.active.is_(True))
        )
        providers = list(result.scalars().all())
        recommendations = []
        warnings = []

        for provider in providers:
            for service in provider.services:
                if not service.active:
                    continue
                if cod_required and not service.cod_supported:
                    continue

                rate = await self._find_rate(
                    provider.id, service.id, origin_country, destination_country, weight
                )
                entry = {
                    "provider_id": str(provider.id),
                    "provider": provider.name,
                    "service_id": str(service.id),
                    "service": service.name,
                    "rank": 0,
                    "why": [],
                    "price": None,
                    "delivery_estimate": None,
                    "evidence": [],
                }

                if rate:
                    entry["price"] = {
                        "amount": float(rate.base_price),
                        "currency": rate.currency,
                        "source": "official_rate",
                        "verified_at": rate.last_verified_at.isoformat() if rate.last_verified_at else None,
                    }
                    entry["why"].append("verified rate available")
                    entry["evidence"].append({"type": "rate", "source_url": rate.source_url})
                else:
                    entry["price"] = {"status": "quote_unavailable"}
                    warnings.append(f"No verified rate for {provider.name}")

                if service.delivery_speed_min_days:
                    entry["delivery_estimate"] = {
                        "min_days": service.delivery_speed_min_days,
                        "max_days": service.delivery_speed_max_days,
                    }
                    if priority == "fastest":
                        entry["why"].append("delivery speed data available")

                recommendations.append(entry)

        recommendations = self._rank(recommendations, priority)
        for i, rec in enumerate(recommendations, 1):
            rec["rank"] = i

        return {"recommendations": recommendations[:5], "warnings": warnings}

    async def _find_rate(
        self,
        provider_id: uuid.UUID,
        service_id: uuid.UUID,
        origin: str,
        destination: str,
        weight: float,
    ) -> ProviderRate | None:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ProviderRate).where(
                ProviderRate.provider_id == provider_id,
                ProviderRate.service_id == service_id,
                ProviderRate.origin_country.ilike(origin),
                ProviderRate.destination_country.ilike(destination),
                ProviderRate.weight_from <= weight,
                ProviderRate.weight_to >= weight,
                ProviderRate.effective_from <= now,
                (ProviderRate.effective_to.is_(None)) | (ProviderRate.effective_to >= now),
            )
        )
        return result.scalars().first()

    def _rank(self, items: list[dict], priority: str) -> list[dict]:
        def score(item: dict) -> float:
            price = item.get("price") or {}
            if price.get("status") == "quote_unavailable":
                return -1.0
            amount = price.get("amount", 999999)
            delivery = (item.get("delivery_estimate") or {}).get("min_days", 30)
            if priority == "cheapest":
                return -amount
            if priority == "fastest":
                return -delivery
            return -(amount * 0.6 + delivery * 100 * 0.4)

        return sorted(items, key=score, reverse=True)
