from datetime import UTC, datetime

from app.integrations.web_search.base import ExtractedWebPage
from app.integrations.web_search.models import SearchResult


class MockWebSearchProvider:
    """Deterministic DEMO search — never invents live prices."""

    name = "mock"

    async def search(
        self,
        query: str,
        *,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[SearchResult]:
        domain = (domains or ["example.com"])[0]
        _ = exclude_domains, search_depth
        return [
            SearchResult(
                title=f"DEMO result for: {query[:60]}",
                url=f"https://{domain}/services",
                snippet=(
                    "DEMO DATA — not a live provider quote. Configure TAVILY_API_KEY "
                    "for real web search. Official provider pages should be verified separately."
                ),
                content=(
                    "DEMO DATA — courier services, COD, tracking and domestic delivery information "
                    "for evaluation. Not a live provider quote."
                ),
                score=0.5,
                publisher="Demo",
                source_type="demo",
                authority_level=6,
                source_domain=domain,
                retrieved_at=datetime.now(UTC),
            )
        ][:max_results]

    async def extract(self, urls: list[str]) -> list[ExtractedWebPage]:
        return [
            ExtractedWebPage(
                url=u,
                title="DEMO extracted page",
                content="DEMO DATA — extraction unavailable without Tavily API key.",
                final_url=u,
            )
            for u in urls
        ]

    async def crawl(self, url: str, *, max_pages: int = 20) -> list[ExtractedWebPage]:
        return await self.extract([url])
