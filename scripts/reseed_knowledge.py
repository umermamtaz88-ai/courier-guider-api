"""Replace demo RAG knowledge with verified provider knowledge (chunked + embedded)."""

from __future__ import annotations

import asyncio

from sqlalchemy import delete, or_, select

from app.ai.rag import RAGService
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeScope, KnowledgeSource

PROVIDER_KNOWLEDGE = [
    (
        "TCS Domestic and International Courier Services",
        "TCS",
        (
            "TCS (TCS Express & Logistics) provides domestic courier services across Pakistan "
            "including overnight express, standard delivery, and international express options. "
            "Common services include COD (cash on delivery), shipment tracking, and business accounts. "
            "Volumetric weight may apply for large or light parcels — confirm the current divisor "
            "on official TCS rate cards. For domestic routes such as Karachi to Lahore, compare "
            "overnight vs economy tiers on price, COD settlement time, and return handling."
        ),
        ["domestic", "international", "cod", "tracking"],
    ),
    (
        "Leopards Courier Services Pakistan",
        "Leopards Courier",
        (
            "Leopards Courier is widely used for e-commerce and COD shipments within Pakistan. "
            "Services include overnight express, economy delivery, warehousing, and fulfillment. "
            "Leopards Box supports self-service drop-off at partner locations. "
            "For clothing and apparel shipments between major cities, compare Leopards economy "
            "and express options on price, COD charges, and delivery SLA. "
            "Return and refused-delivery policies vary by service — verify on leopardscourier.com."
        ),
        ["domestic", "ecommerce", "cod", "returns"],
    ),
    (
        "DHL Express International from Pakistan",
        "DHL",
        (
            "DHL Express handles international express shipping from Pakistan. "
            "Required documentation typically includes commercial invoice, packing list, "
            "and accurate HS codes for clothing and textile exports. "
            "Delivery times and pricing depend on destination zone and service level. "
            "MyDHL+ portal supports online booking and shipment management for Pakistan."
        ),
        ["international", "customs", "documentation", "express"],
    ),
    (
        "Pakistan Domestic Courier Comparison Guide",
        "Courier Guider",
        (
            "When comparing couriers for domestic Pakistan shipments, evaluate: "
            "1) Base rate and volumetric weight rules, "
            "2) COD availability and settlement timeline, "
            "3) Delivery speed (overnight vs economy), "
            "4) Return and refused-delivery charges, "
            "5) Tracking reliability and customer support. "
            "For clothing shipments between Karachi, Lahore, and Islamabad, "
            "TCS and Leopards are the most commonly compared providers."
        ),
        ["domestic", "comparison", "cod", "pricing"],
    ),
    (
        "COD Cash on Delivery Overview Pakistan",
        "Courier Guider",
        (
            "Cash on Delivery (COD) allows recipients to pay upon delivery. "
            "Couriers typically deduct COD handling fees and remit collected amounts "
            "to the shipper on a settlement schedule (often weekly). "
            "Refused COD deliveries may incur return shipping charges. "
            "Compare COD fee percentages and settlement speed when choosing a provider."
        ),
        ["cod", "settlement", "returns"],
    ),
]


async def reseed() -> None:
    from app.config import get_settings
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        demo_filter = or_(
            KnowledgeSource.name.ilike("%(Demo)%"),
            KnowledgeSource.name.ilike("%DEMO%"),
            KnowledgeSource.publisher.ilike("%Demo%"),
        )
        result = await db.execute(select(KnowledgeSource.id).where(demo_filter))
        demo_source_ids = [row[0] for row in result.all()]

        if demo_source_ids:
            docs = await db.execute(
                select(KnowledgeDocument.id).where(
                    KnowledgeDocument.knowledge_source_id.in_(demo_source_ids)
                )
            )
            doc_ids = [row[0] for row in docs.all()]
            if doc_ids:
                await db.execute(
                    delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id.in_(doc_ids))
                )
                await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(doc_ids)))
            await db.execute(delete(KnowledgeSource).where(KnowledgeSource.id.in_(demo_source_ids)))
            await db.flush()
            print(f"Removed {len(demo_source_ids)} demo knowledge sources.")

        rag = RAGService(db)
        for title, publisher, text, topics in PROVIDER_KNOWLEDGE:
            existing = await db.execute(
                select(KnowledgeSource.id).where(KnowledgeSource.name == title)
            )
            if existing.scalar_one_or_none():
                print(f"Skip existing: {title}")
                continue
            doc = await rag.ingest_text(
                title=title,
                text=text,
                scope_type=KnowledgeScope.GLOBAL,
                scope_id=None,
                source_type="official_provider",
                publisher=publisher,
                authority_level=1,
                metadata={"topics": topics, "verified": True},
            )
            chunks = await db.execute(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.knowledge_document_id == doc.id
                )
            )
            chunk_count = len(list(chunks.scalars().all()))
            print(f"Ingested: {title} ({chunk_count} chunks)")

        await db.commit()
        print("Knowledge reseed complete.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(reseed())
