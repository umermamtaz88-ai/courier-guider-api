"""Evidence source helpers for RAG tool results and citations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass
class EvidenceSource:
    """Normalized source payload for tool results and LLM evidence."""

    title: str
    publisher: str | None = None
    url: str | None = None
    content: str | None = None
    page: int | None = None
    final_score: float | None = None
    authority_score: float | None = None
    freshness: str | None = None
    effective_from: str | None = None
    rank: int = 0
    source_type: str = "rag"
    label: str = "STORED_KNOWLEDGE"

    def to_evidence_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "publisher": self.publisher,
            "url": self.url,
            "content": (self.content or "")[:1500],
            "page": self.page,
            "final_score": self.final_score,
            "authority_level": self.authority_score,
            "freshness": self.freshness or "unknown",
            "effective_from": self.effective_from,
            "rank": self.rank,
            "source_type": self.source_type,
            "label": self.label,
            "retrieved_at": datetime.now(UTC).isoformat(),
        }


def from_rag_chunk(raw: dict[str, Any], *, rank: int = 0) -> EvidenceSource:
    """Build an EvidenceSource from a RAG chunk / dict payload."""
    return EvidenceSource(
        title=str(raw.get("title") or "Untitled"),
        publisher=raw.get("publisher"),
        url=raw.get("url") or raw.get("source_url"),
        content=raw.get("content"),
        page=raw.get("page") or raw.get("page_start"),
        final_score=_as_float(raw.get("final_score")),
        authority_score=_as_float(raw.get("authority_score") or raw.get("authority_level")),
        freshness=raw.get("freshness"),
        effective_from=raw.get("effective_from"),
        rank=rank,
        source_type="rag",
        label="STORED_KNOWLEDGE",
    )


def from_web_result(raw: dict[str, Any], *, rank: int = 0) -> EvidenceSource:
    """Build an EvidenceSource from a temporary web search result (not global RAG)."""
    return EvidenceSource(
        title=str(raw.get("title") or "Web result"),
        publisher=raw.get("publisher") or raw.get("source_domain"),
        url=raw.get("url"),
        content=raw.get("content") or raw.get("snippet"),
        page=None,
        final_score=_as_float(raw.get("score")),
        authority_score=_as_float(raw.get("authority_level")),
        freshness=raw.get("freshness") or "current",
        effective_from=None,
        rank=rank,
        source_type="web",
        label="LIVE_SEARCH_RESULT",
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
