import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import RAGService
from app.ai.sources import from_rag_chunk


class RAGTools:
    def __init__(self, db: AsyncSession):
        self.rag = RAGService(db)

    async def search_knowledge(
        self,
        query: str,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None = None,
    ) -> dict:
        """Search Courier Guider's trusted logistics knowledge base."""
        chunks = await self.rag.retrieve(query, tenant_id=tenant_id, shipment_id=shipment_id)
        sources = []
        for i, c in enumerate(chunks):
            raw = {
                "title": c.title,
                "publisher": c.publisher,
                "url": c.source_url,
                "content": c.content,
                "page": c.page_start,
                "final_score": c.final_score,
                "authority_score": c.authority_score,
                "freshness": (c.metadata or {}).get("freshness"),
                "effective_from": c.effective_from.isoformat() if c.effective_from else None,
            }
            sources.append(from_rag_chunk(raw, rank=i).to_evidence_dict())
        return {
            "query": query,
            "count": len(sources),
            "sources": sources,
            "note": "Stored RAG knowledge. Prefer official/government authority. Not live web.",
        }
