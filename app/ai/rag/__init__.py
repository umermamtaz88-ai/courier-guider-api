import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.citations import CitationBuilder
from app.ai.rag.filters import RetrievalFilters
from app.ai.rag.hybrid_retriever import HybridRetriever
from app.ai.rag.ingestion import KnowledgeIngestionService
from app.ai.rag.retrieval import RetrievedChunk
from app.db.models import KnowledgeDocument, KnowledgeScope


class RAGService:
    """Facade over Courier Guider RAG modules."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retriever = HybridRetriever(db)
        self.ingestion = KnowledgeIngestionService(db)
        self.citations = CitationBuilder()

    async def retrieve(
        self,
        query: str,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None = None,
        provider_id: uuid.UUID | None = None,
        jurisdiction: str | None = None,
    ) -> list[RetrievedChunk]:
        filters = RetrievalFilters(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=provider_id,
            jurisdiction=jurisdiction,
        )
        return await self.retriever.retrieve(query, filters)

    async def ingest_text(self, **kwargs) -> KnowledgeDocument:
        return await self.ingestion.ingest_text(**kwargs)

    async def ingest_chunks(self, **kwargs) -> KnowledgeDocument:
        return await self.ingestion.ingest_chunk_dicts(**kwargs)

    async def reindex_source(self, source_id: uuid.UUID) -> dict:
        return await self.ingestion.reindex_source(source_id)

    async def reindex_document(self, document_id: uuid.UUID) -> dict:
        return await self.ingestion.reindex_document(document_id)

    def build_citations(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return self.citations.build(chunks)
