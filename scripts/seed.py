"""Seed provider and knowledge data for Courier Guider."""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models import (
    KnowledgeScope,
    Order,
    OrderItem,
    OrderStatus,
    Provider,
    ProviderCapability,
    ProviderPolicy,
    ProviderRate,
    ProviderService,
    Shipment,
    ShipmentDirection,
    ShipmentItem,
    ShipmentStatus,
    Tenant,
    VolumetricWeightRule,
    Customer,
)
from app.db.session import AsyncSessionLocal
from app.ai.rag import RAGService

DEMO_LABEL = "DEMO DATA — not real pricing or regulatory advice"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Provider).limit(1))
        if existing.scalar_one_or_none():
            print("Seed data already exists, skipping.")
            return

        tenant = Tenant(name="Courier Guider Workspace", slug="courier-guider")
        db.add(tenant)
        await db.flush()

        providers_data = [
            ("TCS", "tcs", "Pakistan", "courier"),
            ("Leopards Courier", "leopards", "Pakistan", "courier"),
            ("DHL Pakistan", "dhl-pk", "Pakistan", "freight_forwarder"),
        ]
        providers: list[Provider] = []
        for name, slug, country, ptype in providers_data:
            p = Provider(name=name, slug=slug, country=country, provider_type=ptype, active=True)
            db.add(p)
            providers.append(p)
        await db.flush()

        services = []
        for p in providers:
            svc = ProviderService(
                provider_id=p.id,
                name="International Express",
                direction="international",
                transport_mode="courier",
                cod_supported=False,
                pickup_supported=True,
                tracking_supported=True,
                returns_supported=True,
                delivery_speed_min_days=3,
                delivery_speed_max_days=7,
                active=True,
            )
            db.add(svc)
            services.append((p, svc))
        await db.flush()

        now = datetime.now(UTC)
        for p, svc in services:
            db.add(
                ProviderRate(
                    provider_id=p.id,
                    service_id=svc.id,
                    origin_country="Pakistan",
                    destination_country="UAE",
                    weight_from=1,
                    weight_to=30,
                    base_price=12000 if p.slug == "tcs" else 13500,
                    currency="PKR",
                    effective_from=now,
                    source_url="https://example.com/demo-rate-card",
                    last_verified_at=now,
                )
            )
            db.add(
                ProviderPolicy(
                    provider_id=p.id,
                    policy_type="return",
                    title=f"{p.name} Return Policy (Demo)",
                    summary=DEMO_LABEL,
                    policy_text="Returned parcels may incur return shipping charges. Customer refund is separate.",
                    effective_from=now,
                    last_verified_at=now,
                )
            )
            db.add(
                ProviderCapability(
                    provider_id=p.id,
                    tracking=True,
                    live_quote=False,
                    availability=True,
                    delivery_estimate=True,
                    returns=True,
                    claims=True,
                    settlements=True,
                    last_verified_at=now,
                )
            )

        shipment = Shipment(
            tenant_id=tenant.id,
            reference_code="SHP-DEMO001",
            direction=ShipmentDirection.EXPORT,
            status=ShipmentStatus.PLANNING,
            origin_country="Pakistan",
            origin_city="Lahore",
            destination_country="UAE",
            destination_city="Dubai",
            total_weight=8,
            weight_unit="kg",
            declared_value=50000,
            declared_currency="PKR",
            provider_id=providers[0].id,
            tracking_number="DEMO-TRK-001",
        )
        db.add(shipment)
        await db.flush()
        db.add(
            ShipmentItem(
                shipment_id=shipment.id,
                description="Clothing assortment",
                category="clothing",
                quantity=1,
                weight=8,
            )
        )

        for p, svc in services:
            db.add(
                VolumetricWeightRule(
                    provider_id=p.id,
                    service_id=svc.id,
                    origin_country="Pakistan",
                    destination_country="UAE",
                    divisor=5000,
                    effective_from=now,
                    source_url="https://example.com/demo-volumetric",
                )
            )

        customer = Customer(
            tenant_id=tenant.id,
            name="Demo Customer",
            email="customer@demo.com",
            phone="03001234567",
            default_address={"city": "Lahore", "country": "Pakistan"},
        )
        db.add(customer)
        await db.flush()
        order = Order(
            tenant_id=tenant.id,
            external_order_id="DEMO-ORD-001",
            platform="mock",
            customer_id=customer.id,
            status=OrderStatus.CONFIRMED,
            currency="PKR",
            total_amount=5000,
            shipping_address={"city": "Lahore", "country": "Pakistan"},
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                order_id=order.id,
                name="T-shirt",
                quantity=2,
                weight=0.5,
            )
        )

        rag = RAGService(db)
        await rag.ingest_text(
            title="Pakistan Export Documentation Overview",
            text=(
                "For commercial exports from Pakistan to UAE and other destinations, businesses typically "
                "prepare a commercial invoice, packing list, and may need certificates depending on product type. "
                "Verify current FBR and customs requirements from official government sources before shipping."
            ),
            scope_type=KnowledgeScope.GLOBAL,
            scope_id=None,
            source_type="government",
            publisher="Pakistan Customs Reference",
            authority_level=2,
        )

        provider_knowledge = [
            (
                "TCS Domestic and International Courier Services",
                "TCS",
                (
                    "TCS provides domestic courier services across Pakistan and international express options. "
                    "Services include COD, tracking, and business accounts. Volumetric weight may apply for "
                    "oversized parcels. Compare price, delivery speed, and COD settlement terms before choosing."
                ),
                ["domestic", "international", "cod", "tracking"],
            ),
            (
                "Leopards Courier E-Commerce and COD",
                "Leopards Courier",
                (
                    "Leopards Courier is commonly used for e-commerce and COD shipments in Pakistan. "
                    "Economy services may use volumetric weight for large boxes. Returns and COD policies "
                    "vary by service — check official policy pages for return charges and settlement timelines."
                ),
                ["domestic", "ecommerce", "cod", "returns"],
            ),
            (
                "DHL Express International from Pakistan",
                "DHL",
                (
                    "DHL Express specializes in international express shipping. Customs documentation, "
                    "commercial invoice, and accurate HS codes are typically required for international "
                    "clothing exports. Delivery times and pricing depend on destination and service level."
                ),
                ["international", "customs", "documentation", "express"],
            ),
        ]
        for title, publisher, text, topics in provider_knowledge:
            await rag.ingest_text(
                title=title,
                text=text,
                scope_type=KnowledgeScope.GLOBAL,
                scope_id=None,
                source_type="official_provider",
                publisher=publisher,
                authority_level=1,
                metadata={"topics": topics, "verified": True},
            )

        await db.commit()
        print("Seed complete.")
        print("Register a new account at /register to sign in.")


if __name__ == "__main__":
    asyncio.run(seed())
