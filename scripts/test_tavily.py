"""Direct Tavily integration tests for Courier Guider web search."""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlparse

from app.config import get_settings
from app.integrations.web_search.errors import classify_tavily_exception
from app.integrations.web_search.registry import get_web_search_provider
from app.integrations.web_search.tavily import TavilyWebSearchProvider


OFFICIAL_DOMAINS = {
    "leopardscourier.com",
    "tcsexpress.com",
    "dhl.com",
}


async def test_query(label: str, query: str) -> dict:
    settings = get_settings()
    provider = get_web_search_provider()
    print(f"\n=== {label} ===")
    print(f"provider={getattr(provider, 'name', 'unknown')}")
    print(f"WEB_SEARCH_PROVIDER={settings.web_search_provider}")
    print(f"TAVILY_API_KEY={'set' if settings.tavily_api_key else 'MISSING'}")
    print(f"TAVILY_SEARCH_DEPTH={settings.tavily_search_depth}")
    print(f"TAVILY_MAX_RESULTS={settings.tavily_max_results}")

    try:
        results = await provider.search(
            query,
            max_results=settings.tavily_max_results,
            search_depth=settings.tavily_search_depth,
        )
        domains = []
        for result in results:
            host = urlparse(result.url).netloc.lower().removeprefix("www.")
            domains.append(host)
            print(f"- {result.title[:80]}")
            print(f"  url={result.url}")
            print(f"  type={result.source_type} authority={result.authority_level}")
        official_hits = [d for d in domains if any(o in d for o in OFFICIAL_DOMAINS)]
        return {
            "ok": True,
            "count": len(results),
            "domains": domains,
            "official_domains": official_hits,
            "has_urls": all(r.url for r in results),
        }
    except Exception as exc:
        code, status, message = classify_tavily_exception(exc)
        print(f"ERROR code={code} http_status={status}")
        print(f"message={message[:300]}")
        return {
            "ok": False,
            "error_code": code,
            "http_status": status,
            "message": message,
        }


async def main() -> None:
    settings = get_settings()
    if settings.web_search_provider.lower() != "tavily":
        print("WEB_SEARCH_PROVIDER is not 'tavily' — set it in .env to test live Tavily.")
    if not settings.tavily_api_key:
        print("TAVILY_API_KEY is missing — Tavily live tests will fail.")

  # quick auth probe without printing the key
    if isinstance(get_web_search_provider(), TavilyWebSearchProvider):
        print("Tavily provider selected.")

    queries = [
        ("Leopards", "Leopards Pakistan courier services"),
        ("TCS", "TCS Pakistan courier services"),
        ("DHL", "DHL Pakistan shipping services"),
    ]
    outcomes = []
    for label, query in queries:
        outcomes.append(await test_query(label, query))

    failed = [o for o in outcomes if not o.get("ok")]
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
