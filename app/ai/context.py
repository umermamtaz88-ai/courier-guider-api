import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.ai.rag.retrieval import RetrievedChunk


class EvidencePackage(BaseModel):
    query: str
    intent: str
    answer_type: str = "general_answer"
    parsed_query: dict = Field(default_factory=dict)
    short_memory: dict = Field(default_factory=dict)
    long_memory: dict = Field(default_factory=dict)
    shipment: dict = Field(default_factory=dict)
    current_live_data: list[dict] = Field(default_factory=list)
    database_facts: list[dict] = Field(default_factory=list)
    open_issues: list[dict] = Field(default_factory=list)
    retrieved_rag_sources: list[dict] = Field(default_factory=list)
    web_search_results: list[dict] = Field(default_factory=list)
    private_attachments: list[dict] = Field(default_factory=list)
    tool_results: list[dict] = Field(default_factory=list)
    recommendations: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requested_action: str = ""
    missing_information: list[str] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)


class AgentContext(BaseModel):
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    shipment_id: uuid.UUID | None = None
    intent: str
    evidence: EvidencePackage
    allowed_tools: list[str] = Field(default_factory=list)


def chunk_to_source_dict(chunk: RetrievedChunk) -> dict:
    # Prefer label set by hybrid retriever; fall back to score bands
    freshness = (chunk.metadata or {}).get("freshness") if chunk.metadata else None
    if not freshness:
        if chunk.currentness_score >= 0.95:
            freshness = "current"
        elif chunk.currentness_score >= 0.65:
            freshness = "recent"
        elif chunk.currentness_score >= 0.35:
            freshness = "unknown"
        elif chunk.currentness_score > 0:
            freshness = "stale"
        else:
            freshness = "expired"
    return {
        "chunk_id": str(chunk.chunk_id),
        "source_id": str(chunk.source_id),
        "title": chunk.title,
        "publisher": chunk.publisher,
        "url": chunk.source_url,
        "content": chunk.content[:1500],
        "page": chunk.page_start,
        "authority_level": chunk.authority_score,
        "currentness_score": chunk.currentness_score,
        "final_score": chunk.final_score,
        "freshness": freshness,
        "freshness_ui": (
            "current"
            if freshness in ("current", "recent")
            else "outdated"
            if freshness in ("stale", "expired")
            else "unknown"
        ),
        "effective_from": chunk.effective_from.isoformat() if chunk.effective_from else None,
        "effective_to": chunk.effective_to.isoformat() if chunk.effective_to else None,
        "source_type": (chunk.metadata or {}).get("source_type")
        or ("official_provider" if chunk.authority_score and chunk.authority_score <= 2 else "secondary"),
        "label": "STORED_KNOWLEDGE",
        "provider": (chunk.metadata or {}).get("provider")
        or _infer_provider_name(chunk.publisher, chunk.title, chunk.source_url),
    }


def _infer_provider_name(publisher, title, url):
    from app.ai.providers_catalog import infer_provider_from_source

    return infer_provider_from_source(publisher=publisher, title=title, url=url)
