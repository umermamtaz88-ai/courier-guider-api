import uuid

from app.integrations.commerce.base import CommerceOrder


class MockCommerceAdapter:
    platform = "mock"
    label = "DEMO"

    async def list_orders(self, *, tenant_id: uuid.UUID, since: str | None = None) -> list[CommerceOrder]:
        return [
            CommerceOrder(
                external_order_id="DEMO-ORD-001",
                platform="mock",
                customer_name="Demo Customer",
                customer_email="customer@demo.com",
                currency="PKR",
                total_amount=5000,
                shipping_address={"city": "Lahore", "country": "Pakistan"},
                items=[{"name": "T-shirt", "quantity": 2, "weight": 0.5}],
            )
        ]

    async def get_order(self, *, tenant_id: uuid.UUID, external_order_id: str) -> CommerceOrder | None:
        orders = await self.list_orders(tenant_id=tenant_id)
        for o in orders:
            if o.external_order_id == external_order_id:
                return o
        return None
