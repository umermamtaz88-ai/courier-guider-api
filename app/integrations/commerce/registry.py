import uuid

from app.integrations.commerce.base import CommercePlatformAdapter
from app.integrations.commerce.mock import MockCommerceAdapter


class CommerceRegistry:
    def get(self, platform: str) -> CommercePlatformAdapter | None:
        if platform in ("mock", "manual"):
            return MockCommerceAdapter()
        return None
