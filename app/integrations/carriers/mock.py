import uuid
from datetime import UTC, datetime

from app.integrations.carriers.base import (
    AvailabilityRequest,
    AvailabilityResult,
    QuoteRequest,
    QuoteResult,
    TrackingResult,
)


class MockCarrierAdapter:
    """DEMO/MOCK carrier — clearly labeled, never simulates real bookings."""

    provider_slug = "mock"
    label = "DEMO / MOCK"

    def __init__(self, provider_id: uuid.UUID, provider_name: str):
        self.provider_id = provider_id
        self.provider_name = provider_name

    async def get_tracking(self, tracking_number: str) -> TrackingResult:
        now = datetime.now(UTC)
        return TrackingResult(
            provider_id=self.provider_id,
            tracking_number=tracking_number,
            status=f"{self.label}: in_transit",
            status_category="in_transit",
            location="Lahore Hub (demo)",
            description="Mock tracking event for development",
            event_time=now,
            retrieved_at=now,
            external_reference=tracking_number,
            source="mock_provider",
        )

    async def get_quote(self, request: QuoteRequest) -> QuoteResult:
        now = datetime.now(UTC)
        return QuoteResult(
            provider_id=self.provider_id,
            service_id=request.service_id,
            available=True,
            amount=None,
            currency="PKR",
            delivery_min_days=3,
            delivery_max_days=7,
            breakdown={"note": self.label},
            quoted_at=now,
            source="estimate",
        )

    async def get_service_availability(self, request: AvailabilityRequest) -> AvailabilityResult:
        return AvailabilityResult(
            provider_id=self.provider_id,
            available=True,
            retrieved_at=datetime.now(UTC),
            source="mock_provider",
            details={"label": self.label},
        )
