import re
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource, Shipment

IDENTIFIER_PATTERNS = [
    re.compile(r"\bSHP-[A-Z0-9]{6,}\b", re.I),
    re.compile(r"\b[A-Z]{2,4}\d{8,15}\b"),
    re.compile(r"\bDEMO-ORD-\d+\b", re.I),
]


def extract_identifiers(query: str) -> list[str]:
    found: list[str] = []
    for pattern in IDENTIFIER_PATTERNS:
        found.extend(m.group(0) for m in pattern.finditer(query))
    return list(dict.fromkeys(found))


async def search_by_identifiers(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    query: str,
) -> list[dict]:
    """Exact-match lookup for tracking numbers and reference codes."""
    identifiers = extract_identifiers(query)
    if not identifiers:
        return []

    results: list[dict] = []
    shipment_stmt = select(Shipment).where(
        Shipment.tenant_id == tenant_id,
        or_(
            Shipment.reference_code.in_(identifiers),
            Shipment.tracking_number.in_(identifiers),
            Shipment.external_order_id.in_(identifiers),
        ),
    )
    shipment_result = await db.execute(shipment_stmt)
    for shipment in shipment_result.scalars().all():
        results.append({
            "type": "shipment",
            "identifier": shipment.reference_code,
            "shipment_id": str(shipment.id),
            "status": shipment.status.value if hasattr(shipment.status, "value") else str(shipment.status),
            "tracking_number": shipment.tracking_number,
        })

    for ident in identifiers:
        chunk_stmt = (
            select(KnowledgeChunk, KnowledgeDocument, KnowledgeSource)
            .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
            .join(KnowledgeSource, KnowledgeDocument.knowledge_source_id == KnowledgeSource.id)
            .where(KnowledgeChunk.content.ilike(f"%{ident}%"))
            .limit(3)
        )
        chunk_result = await db.execute(chunk_stmt)
        for chunk, doc, source in chunk_result.all():
            results.append({
                "type": "knowledge",
                "identifier": ident,
                "chunk_id": str(chunk.id),
                "title": doc.title,
                "source": source.name,
            })

    return results
