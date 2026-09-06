"""Normalized web search result models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str
    url: str
    content: str | None = None
    snippet: str | None = None
    published_at: datetime | None = None
    source_domain: str
    provider: str | None = None
    retrieved_at: datetime
    score: float | None = None
    source_type: str = "general"
    authority_level: int = 5
    publisher: str | None = None

    def to_evidence_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": (self.snippet or self.content or "")[:800],
            "source_type": self.source_type,
            "authority_level": self.authority_level,
            "publisher": self.publisher,
            "freshness": "current",
            "retrieved_at": self.retrieved_at.isoformat(),
            "label": "LIVE_SEARCH_RESULT",
            "source_domain": self.source_domain,
        }
