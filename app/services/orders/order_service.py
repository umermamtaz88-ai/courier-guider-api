import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Customer, Order, OrderItem, OrderShipmentLink, OrderStatus
from app.integrations.commerce.base import CommerceOrder
from app.services.shipments.shipment_service import ShipmentService


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.shipments = ShipmentService(db)

    async def import_order(self, tenant_id: uuid.UUID, data: CommerceOrder) -> Order:
        customer = Customer(
            tenant_id=tenant_id,
            name=data.customer_name,
            email=data.customer_email,
            phone=data.customer_phone,
            default_address=data.shipping_address,
        )
        self.db.add(customer)
        await self.db.flush()

        order = Order(
            tenant_id=tenant_id,
            external_order_id=data.external_order_id,
            platform=data.platform,
            customer_id=customer.id,
            status=OrderStatus.CONFIRMED,
            currency=data.currency,
            total_amount=data.total_amount,
            shipping_address=data.shipping_address,
        )
        self.db.add(order)
        await self.db.flush()

        for item in data.items:
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    name=item.get("name", "Item"),
                    quantity=item.get("quantity", 1),
                    unit_price=item.get("unit_price"),
                    weight=item.get("weight"),
                    dimensions=item.get("dimensions"),
                )
            )
        await self.db.flush()
        return order

    async def convert_to_shipment(self, tenant_id: uuid.UUID, order_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
        )
        order = result.scalar_one_or_none()
        if order is None:
            return {"error": "order_not_found"}

        addr = order.shipping_address or {}
        total_weight = sum((i.weight or 0) * (i.quantity or 1) for i in order.items)

        shipment = await self.shipments.create(tenant_id, {
            "external_order_id": order.external_order_id,
            "origin_country": "Pakistan",
            "origin_city": "Lahore",
            "destination_country": addr.get("country", "Pakistan"),
            "destination_city": addr.get("city"),
            "total_weight": total_weight or 1,
            "declared_value": float(order.total_amount) if order.total_amount else None,
            "declared_currency": order.currency,
        })

        self.db.add(OrderShipmentLink(order_id=order.id, shipment_id=shipment.id))
        order.fulfillment_status = "shipment_created"
        order.status = OrderStatus.FULFILLED
        await self.db.flush()

        return {"order_id": str(order.id), "shipment_id": str(shipment.id), "reference_code": shipment.reference_code}
