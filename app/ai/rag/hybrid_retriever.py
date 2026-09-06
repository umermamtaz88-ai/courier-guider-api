import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.openai import get_embedding_provider
from app.ai.rag.currentness import currentness_score
from app.ai.rag.filters import RetrievalFilters, build_scope_filter, extract_query_entities
from app.ai.rag.reranking import rerank_chunks
from app.ai.rag.retrieval import RetrievedChunk
from app.ai.rag.source_ranking import authority_score, compute_final_score
from app.config import get_settings
from app.db.models import KnowledgeChunk, KnowledgeDocument, KnowledgeSource


class HybridRetriever:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def retrieve(self, query: str, filters: RetrievalFilters) -> list[RetrievedChunk]:
        top_k = self.settings.rag_top_k
        final_k = self.settings.rag_final_k
        entities = extract_query_entities(query)

        stmt = (
            select(KnowledgeChunk, KnowledgeDocument, KnowledgeSource)
            .join(KnowledgeDocument, KnowledgeChunk.knowledge_document_id == KnowledgeDocument.id)
            .join(KnowledgeSource, KnowledgeDocument.knowledge_source_id == KnowledgeSource.id)
            .where(KnowledgeSource.status == "active", build_scope_filter(filters))
        )

        if filters.jurisdiction:
            stmt = stmt.where(KnowledgeSource.jurisdiction.ilike(filters.jurisdiction))
        if filters.provider_id:
            stmt = stmt.where(
                KnowledgeChunk.chunk_metadata["provider_id"].astext == str(filters.provider_id)
            )

        vector_chunks: list[RetrievedChunk] = []
        keyword_chunks: list[RetrievedChunk] = []

        try:
            embedder = get_embedding_provider()
            query_vec = await embedder.embed_query(query)
            vstmt = stmt.order_by(KnowledgeChunk.embedding.cosine_distance(query_vec)).limit(top_k)
            vresult = await self.db.execute(vstmt)
            for idx, (chunk, doc, source) in enumerate(vresult.all()):
                semantic = max(0.0, 1.0 - idx * 0.04)
                vector_chunks.append(self._to_chunk(chunk, doc, source, semantic_score=semantic, keyword_score=0.0))
        except Exception:
            pass

        terms = _extract_search_terms(query)
        if terms:
            kw_filter = or_(*[KnowledgeChunk.content.ilike(f"%{t}%") for t in terms])
            kstmt = stmt.where(kw_filter).limit(top_k)
            kresult = await self.db.execute(kstmt)
            for idx, (chunk, doc, source) in enumerate(kresult.all()):
                keyword = max(0.0, 1.0 - idx * 0.05)
                keyword_chunks.append(self._to_chunk(chunk, doc, source, semantic_score=0.0, keyword_score=keyword))

        if terms:
            try:
                ts_query = " | ".join(terms)
                tstmt = (
                    stmt.where(
                        KnowledgeChunk.search_vector.isnot(None),
                        KnowledgeChunk.search_vector.op("@@")(func.plainto_tsquery("english", ts_query)),
                    )
                    .limit(top_k)
                )
                tresult = await self.db.execute(tstmt)
                for idx, (chunk, doc, source) in enumerate(tresult.all()):
                    keyword = max(0.85, 1.0 - idx * 0.04)
                    keyword_chunks.append(self._to_chunk(chunk, doc, source, semantic_score=0.0, keyword_score=keyword))
            except Exception:
                pass

        merged = {str(c.chunk_id): c for c in vector_chunks + keyword_chunks}
        for chunk in merged.values():
            if entities.get("topics") and chunk.metadata:
                topics = [t.lower() for t in entities["topics"]]
                if any(t in (chunk.metadata.get("policy_type") or "").lower() for t in topics):
                    chunk.applicability_score = 1.0

        return rerank_chunks(list(merged.values()), final_k)

    def _to_chunk(self, chunk, doc, source, *, semantic_score: float, keyword_score: float) -> RetrievedChunk:
        curr = currentness_score(source.effective_from, source.effective_to)
        auth = authority_score(source.authority_level)
        final = compute_final_score(
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            authority_level=source.authority_level,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
        )
        return RetrievedChunk(
            chunk_id=chunk.id,
            content=chunk.content,
            source_id=source.id,
            title=doc.title,
            publisher=source.publisher,
            source_url=source.source_url,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            authority_score=auth,
            currentness_score=curr,
            final_score=final,
            effective_from=source.effective_from,
            effective_to=source.effective_to,
            metadata=chunk.chunk_metadata,
        )


EXACT_TERMS = {
    "tcs", "leopards", "dhl", "cod", "awb", "hs", "invoice", "refund", "tracking", "ndr", "m&p", "trax",
}


def _extract_search_terms(query: str) -> list[str]:
    lower = query.lower()
    terms: list[str] = []
    for term in EXACT_TERMS:
        if term in lower:
            terms.append(term)
    for word in query.split():
        clean = word.strip(".,?!").lower()
        if len(clean) > 3 or clean in EXACT_TERMS:
            terms.append(clean)
    return list(dict.fromkeys(terms))[:8]
