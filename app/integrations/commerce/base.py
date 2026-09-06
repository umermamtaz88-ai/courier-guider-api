import uuid
from typing import Protocol

from pydantic import BaseModel


class CommerceOrder(BaseModel):
    external_order_id: str
    platform: str
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    currency: str = "PKR"
    total_amount: float | None = None
    shipping_address: dict | None = None
    items: list[dict] = []


class CommercePlatformAdapter(Protocol):
    platform: str

    async def list_orders(self, *, tenant_id: uuid.UUID, since: str | None = None) -> list[CommerceOrder]: ...

    async def get_order(self, *, tenant_id: uuid.UUID, external_order_id: str) -> CommerceOrder | None: ...
