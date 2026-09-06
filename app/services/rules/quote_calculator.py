import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Provider, ProviderService, VolumetricWeightRule
from app.services.rules.quote_engine import calculate_billable_weight, calculate_quote_breakdown, calculate_volumetric_weight
from datetime import UTC, datetime
from decimal import Decimal


class QuoteCalculatorService:
    """Deterministic quote calculation with volumetric weight and assumptions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate(
        self,
        *,
        provider_id: uuid.UUID,
        service_id: uuid.UUID | None,
        actual_weight_kg: float,
        length_cm: float | None = None,
        width_cm: float | None = None,
        height_cm: float | None = None,
        origin_country: str,
        destination_country: str,
        cod_enabled: bool = False,
        base_rate: Decimal | None = None,
    ) -> dict:
        divisor = await self._get_divisor(provider_id, service_id, origin_country, destination_country)
        volumetric_kg = 0.0
        if length_cm and width_cm and height_cm and divisor:
            volumetric_kg = calculate_volumetric_weight(length_cm, width_cm, height_cm, divisor)

        billable = calculate_billable_weight(actual_weight_kg, volumetric_kg)
        base = base_rate or Decimal("0")
        cod_fee = Decimal("100") if cod_enabled else Decimal("0")
        fuel = (base * Decimal("0.1")).quantize(Decimal("0.01"))
        breakdown = calculate_quote_breakdown(base_charge=base, fuel_surcharge=fuel, cod_fee=cod_fee)

        assumptions = [
            f"{actual_weight_kg}kg actual weight",
            f"{billable}kg billable weight",
            f"volumetric divisor {divisor}" if divisor else "no dimensions supplied",
            "COD fee applied" if cod_enabled else "COD not selected",
            "stored official rate" if base_rate else "rate unavailable",
        ]

        return {
            "provider_id": str(provider_id),
            "billable_weight": billable,
            "actual_weight": actual_weight_kg,
            "volumetric_weight": volumetric_kg,
            "breakdown": breakdown,
            "assumptions": assumptions,
            "source": "official_rate" if base_rate else "quote_unavailable",
            "currency": "PKR",
        }

    async def _get_divisor(
        self, provider_id: uuid.UUID, service_id: uuid.UUID | None, origin: str, dest: str
    ) -> int | None:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(VolumetricWeightRule).where(
                VolumetricWeightRule.provider_id == provider_id,
                VolumetricWeightRule.effective_from <= now,
                (VolumetricWeightRule.effective_to.is_(None)) | (VolumetricWeightRule.effective_to >= now),
            )
        )
        rule = result.scalars().first()
        return rule.divisor if rule else 5000
