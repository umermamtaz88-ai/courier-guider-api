import uuid
from datetime import datetime

from pydantic import BaseModel


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    content: str
    source_id: uuid.UUID
    title: str
    publisher: str | None = None
    source_url: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    authority_score: float = 0.0
    currentness_score: float = 1.0
    applicability_score: float = 1.0
    final_score: float = 0.0
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    metadata: dict | None = None
