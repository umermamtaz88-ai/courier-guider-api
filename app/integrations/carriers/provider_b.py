"""Leopards demo adapter — labeled DEMO."""

import uuid

from app.integrations.carriers.mock import MockCarrierAdapter


class LeopardsAdapter(MockCarrierAdapter):
    provider_slug = "leopards"

    def __init__(self, provider_id: uuid.UUID):
        super().__init__(provider_id=provider_id, provider_name="Leopards Courier")

    async def get_tracking(self, tracking_number: str):
        result = await super().get_tracking(tracking_number)
        result.location = "Leopards Karachi Hub (DEMO)"
        return result
