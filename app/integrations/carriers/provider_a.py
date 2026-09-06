"""TCS demo adapter — labeled DEMO, uses mock behavior."""

import uuid
from datetime import UTC, datetime

from app.integrations.carriers.mock import MockCarrierAdapter


class TCSAdapter(MockCarrierAdapter):
    provider_slug = "tcs"

    def __init__(self, provider_id: uuid.UUID):
        super().__init__(provider_id=provider_id, provider_name="TCS")

    async def get_tracking(self, tracking_number: str):
        result = await super().get_tracking(tracking_number)
        result.location = "TCS Lahore Hub (DEMO)"
        result.description = "TCS demo tracking event"
        return result
