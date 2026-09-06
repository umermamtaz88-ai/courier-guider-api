import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.openai import get_embedding_provider
from app.ai.rag.chunking import semantic_chunk
from app.db.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeScope,
    KnowledgeSource,
)
from app.logging import get_logger

logger = get_logger("courier_guider.ingestion")


class KnowledgeIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_text(
        self,
        *,
        title: str,
        text: str,
        scope_type: KnowledgeScope,
        scope_id: uuid.UUID | None,
        source_type: str,
        publisher: str | None,
        authority_level: int = 3,
        document_type: str = "text",
        metadata: dict | None = None,
        jurisdiction: str | None = None,
        effective_from=None,
        effective_to=None,
        chunks: list[dict] | None = None,
    ) -> KnowledgeDocument:
        source = KnowledgeSource(
            scope_type=scope_type,
            scope_id=scope_id,
            source_type=source_type,
            authority_level=authority_level,
            name=title,
            publisher=publisher,
            jurisdiction=jurisdiction,
            status="active",
            effective_from=effective_from,
            effective_to=effective_to,
            last_success_at=datetime.now(UTC),
        )
        self.db.add(source)
        await self.db.flush()

        doc = KnowledgeDocument(
            knowledge_source_id=source.id,
            title=title,
            document_type=document_type,
            raw_text=text,
            clean_text=text,
            doc_metadata=metadata,
        )
        self.db.add(doc)
        await self.db.flush()

        content_hash = (metadata or {}).get("content_hash") or hashlib.sha256(
            text.encode("utf-8", errors="ignore")
        ).hexdigest()
        version = KnowledgeDocumentVersion(
            document_id=doc.id,
            version=1,
            content_hash=content_hash,
            raw_content=text[:50000],
            clean_content=text[:50000],
            crawled_at=datetime.now(UTC),
            status="ACTIVE",
        )
        self.db.add(version)
        await self.db.flush()

        chunk_payloads = chunks if chunks is not None else semantic_chunk(text)
        await self._persist_chunks(doc.id, version.id, chunk_payloads, metadata)
        await self.db.flush()
        return doc

    async def ingest_chunk_dicts(
        self,
        *,
        title: str,
        text: str,
        chunks: list[dict],
        scope_type: KnowledgeScope,
        scope_id: uuid.UUID | None,
        source_type: str,
        publisher: str | None,
        authority_level: int = 3,
        document_type: str = "pdf",
        metadata: dict | None = None,
        jurisdiction: str | None = None,
    ) -> KnowledgeDocument:
        """Ingest pre-built semantic/page-aware chunks (e.g. from PDF)."""
        return await self.ingest_text(
            title=title,
            text=text,
            scope_type=scope_type,
            scope_id=scope_id,
            source_type=source_type,
            publisher=publisher,
            authority_level=authority_level,
            document_type=document_type,
            metadata=metadata,
            jurisdiction=jurisdiction,
            chunks=chunks,
        )

    async def reindex_document(self, document_id: uuid.UUID) -> dict:
        """Rebuild embeddings + TSVECTOR for all chunks of a document."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.knowledge_document_id == document_id)
        )
        chunks = list(result.scalars().all())
        if not chunks:
            return {"document_id": str(document_id), "reindexed": 0}

        texts = [c.content for c in chunks]
        embeddings: list[list[float]] = []
        embed_error: str | None = None
        try:
            embedder = get_embedding_provider()
            embeddings = await embedder.embed_texts(texts)
        except Exception as exc:
            embed_error = str(exc)[:300]
            logger.warning("reindex_embed_failed", document_id=str(document_id), error=embed_error)

        for i, chunk in enumerate(chunks):
            if i < len(embeddings) and embeddings[i]:
                chunk.embedding = embeddings[i]
            await self._update_tsvector(chunk.id)

        await self.db.flush()
        return {
            "document_id": str(document_id),
            "reindexed": len(chunks),
            "embed_error": embed_error,
        }

    async def reindex_source(self, source_id: uuid.UUID) -> dict:
        from sqlalchemy import select

        docs = await self.db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.knowledge_source_id == source_id)
        )
        totals = []
        for doc in docs.scalars().all():
            totals.append(await self.reindex_document(doc.id))
        return {
            "source_id": str(source_id),
            "documents": totals,
            "chunk_total": sum(t.get("reindexed", 0) for t in totals),
        }

    async def _persist_chunks(
        self,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        chunks: list[dict],
        metadata: dict | None,
    ) -> None:
        texts = [c.get("content") or "" for c in chunks]
        embeddings: list[list[float]] = []
        try:
            embedder = get_embedding_provider()
            embeddings = await embedder.embed_texts(texts)
        except Exception as exc:
            logger.warning("ingest_embed_failed", error=str(exc)[:300])
            embeddings = [[] for _ in texts]

        chunk_ids: list[uuid.UUID] = []
        for i, chunk_data in enumerate(chunks):
            content = (chunk_data.get("content") or "").strip()
            if not content:
                continue
            chunk_meta = dict(metadata or {})
            chunk_meta.update(chunk_data.get("metadata") or {})
            if chunk_data.get("section_title"):
                chunk_meta["policy_type"] = chunk_data["section_title"]
            chunk = KnowledgeChunk(
                knowledge_document_id=document_id,
                version_id=version_id,
                chunk_index=chunk_data.get("chunk_index", i),
                content=content,
                section_title=chunk_data.get("section_title"),
                page_start=chunk_data.get("page_start"),
                page_end=chunk_data.get("page_end"),
                chunk_metadata=chunk_meta,
                embedding=embeddings[i] if i < len(embeddings) and embeddings[i] else None,
            )
            self.db.add(chunk)
            await self.db.flush()
            chunk_ids.append(chunk.id)

        for chunk_id in chunk_ids:
            await self._update_tsvector(chunk_id)

    async def _update_tsvector(self, chunk_id: uuid.UUID) -> None:
        try:
            await self.db.execute(
                text(
                    "UPDATE knowledge_chunks SET search_vector = to_tsvector('english', content) WHERE id = :id"
                ),
                {"id": chunk_id},
            )
        except Exception as exc:
            logger.warning("tsvector_update_failed", chunk_id=str(chunk_id), error=str(exc)[:200])
