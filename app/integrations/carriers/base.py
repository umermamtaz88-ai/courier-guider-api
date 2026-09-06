import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class TrackingResult(BaseModel):
    provider_id: uuid.UUID
    tracking_number: str
    status: str
    status_category: Literal[
        "label_created",
        "picked_up",
        "in_transit",
        "customs",
        "out_for_delivery",
        "delivered",
        "delivery_failed",
        "returned",
        "exception",
        "unknown",
    ] = "unknown"
    location: str | None = None
    description: str | None = None
    event_time: datetime | None = None
    retrieved_at: datetime
    external_reference: str | None = None
    source: str = "provider_api"
    raw_data_reference: str | None = None
    stale: bool = False


class QuoteRequest(BaseModel):
    provider_id: uuid.UUID
    service_id: uuid.UUID | None = None
    origin_country: str
    destination_country: str
    weight: float
    weight_unit: str = "kg"


class QuoteResult(BaseModel):
    provider_id: uuid.UUID
    service_id: uuid.UUID | None = None
    available: bool = True
    amount: Decimal | None = None
    currency: str | None = None
    delivery_min_days: int | None = None
    delivery_max_days: int | None = None
    breakdown: dict = Field(default_factory=dict)
    quoted_at: datetime
    expires_at: datetime | None = None
    source: Literal["provider_api", "official_rate", "manual_quote", "estimate"] = "provider_api"
    stale: bool = False


class AvailabilityRequest(BaseModel):
    provider_id: uuid.UUID
    origin_country: str
    destination_country: str


class AvailabilityResult(BaseModel):
    provider_id: uuid.UUID
    available: bool
    retrieved_at: datetime
    source: str = "provider_api"
    details: dict = Field(default_factory=dict)


class CarrierAdapter(Protocol):
    provider_slug: str

    async def get_tracking(self, tracking_number: str) -> TrackingResult: ...

    async def get_quote(self, request: QuoteRequest) -> QuoteResult: ...

    async def get_service_availability(self, request: AvailabilityRequest) -> AvailabilityResult: ...
