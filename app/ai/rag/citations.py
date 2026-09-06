import uuid
from datetime import datetime

from pydantic import BaseModel

from app.ai.rag.retrieval import RetrievedChunk


class Citation(BaseModel):
    source_id: uuid.UUID
    chunk_id: uuid.UUID
    title: str
    publisher: str | None
    page: int | None = None
    source_url: str | None = None
    effective_from: datetime | None = None


class CitationBuilder:
    def build(self, chunks: list[RetrievedChunk]) -> list[dict]:
        citations: list[dict] = []
        seen: set[str] = set()
        for chunk in chunks:
            key = str(chunk.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                Citation(
                    source_id=chunk.source_id,
                    chunk_id=chunk.chunk_id,
                    title=chunk.title,
                    publisher=chunk.publisher,
                    page=chunk.page_start,
                    source_url=chunk.source_url,
                    effective_from=chunk.effective_from,
                ).model_dump(mode="json")
            )
        return citations
