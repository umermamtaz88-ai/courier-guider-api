from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    score: float | None = None
    publisher: str | None = None
    source_type: str = "general"
    authority_level: int = 5
    raw: dict = field(default_factory=dict)


@dataclass
class ExtractedWebPage:
    url: str
    title: str | None
    content: str
    final_url: str | None = None
    raw: dict = field(default_factory=dict)


class WebSearchProvider(Protocol):
    name: str

    async def search(
        self,
        query: str,
        *,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[SearchResult]: ...

    async def extract(self, urls: list[str]) -> list[ExtractedWebPage]: ...

    async def crawl(self, url: str, *, max_pages: int = 20) -> list[ExtractedWebPage]: ...
