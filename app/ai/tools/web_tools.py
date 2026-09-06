"""Web search tools for the agent tool loop (temporary evidence only)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.sources import from_web_result
from app.services.web_search.web_search_service import WebSearchService


class WebTools:
    def __init__(self, db: AsyncSession):
        self.web_search = WebSearchService(db)

    async def search_web(
        self,
        query: str,
        *,
        tenant_id: uuid.UUID,
        providers: list[str] | None = None,
        max_results: int = 5,
    ) -> dict:
        """
        Run live web search for current information.

        Results are temporary evidence for the LLM — they are NOT written
        into global RAG knowledge.
        """
        search_query = self.web_search.build_query(query, providers=providers)
        domains = self.web_search.domains_for_providers(providers)
        outcome = await self.web_search.search(
            tenant_id=tenant_id,
            query=search_query,
            domains=domains,
            max_results=max_results,
        )
        sources = []
        for i, item in enumerate(outcome.results or []):
            if isinstance(item, dict):
                sources.append(from_web_result(item, rank=i).to_evidence_dict())
            elif hasattr(item, "to_evidence_dict"):
                sources.append(item.to_evidence_dict())

        return {
            "query": search_query,
            "provider": outcome.provider,
            "count": len(sources),
            "sources": sources,
            "error_code": outcome.error_code,
            "error_message": outcome.error_message,
            "note": (
                "LIVE web evidence only. Do not treat as persistent global knowledge. "
                "Prefer official provider / government domains when present."
            ),
        }
