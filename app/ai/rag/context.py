import uuid

from app.ai.context import EvidencePackage
from app.ai.rag.retrieval import RetrievedChunk


class RAGContextBuilder:
    """Builds RAG portion of the evidence package."""

    def build_sources(self, chunks: list[RetrievedChunk]) -> list[dict]:
        return [
            {
                "chunk_id": str(c.chunk_id),
                "source_id": str(c.source_id),
                "title": c.title,
                "publisher": c.publisher,
                "content": c.content[:1500],
                "page": c.page_start,
                "authority_score": c.authority_score,
                "currentness_score": c.currentness_score,
                "final_score": c.final_score,
            }
            for c in chunks
        ]

    def merge_into_evidence(
        self,
        evidence: EvidencePackage,
        chunks: list[RetrievedChunk],
    ) -> EvidencePackage:
        evidence.retrieved_rag_sources = self.build_sources(chunks)
        return evidence
