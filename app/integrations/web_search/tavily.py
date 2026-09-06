from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.integrations.web_search.base import ExtractedWebPage
from app.integrations.web_search.errors import TavilySearchError, classify_tavily_http
from app.integrations.web_search.models import SearchResult
from app.logging import get_logger

logger = get_logger("courier_guider.tavily")


class TavilyWebSearchProvider:
    name = "tavily"
    BASE_URL = "https://api.tavily.com"

    def __init__(self, api_key: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.tavily_api_key
        self.max_retries = 2
        self.retry_base_seconds = 1.0
        self.retry_max_seconds = 8.0

    async def search(
        self,
        query: str,
        *,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[SearchResult]:
        if not self.api_key:
            raise TavilySearchError(
                code="TAVILY_API_KEY_MISSING",
                message="TAVILY_API_KEY is not configured.",
            )

        payload: dict = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": False,
        }
        if domains:
            payload["include_domains"] = [d for d in domains if d]
        if exclude_domains:
            payload["exclude_domains"] = [d for d in exclude_domains if d]

        data = await self._post_json("/search", payload)
        results: list[SearchResult] = []
        for item in data.get("results", [])[:max_results]:
            try:
                normalized = _normalize_result(item)
            except Exception as exc:
                logger.warning("tavily_result_parse_failed", error=str(exc)[:200])
                continue
            if normalized is not None:
                results.append(normalized)
        return results

    async def extract(self, urls: list[str]) -> list[ExtractedWebPage]:
        if not self.api_key:
            raise TavilySearchError(
                code="TAVILY_API_KEY_MISSING",
                message="TAVILY_API_KEY is not configured.",
            )

        data = await self._post_json("/extract", {"api_key": self.api_key, "urls": urls})
        pages = []
        for item in data.get("results", []):
            pages.append(
                ExtractedWebPage(
                    url=item.get("url", ""),
                    title=item.get("title"),
                    content=item.get("raw_content") or item.get("content") or "",
                    final_url=item.get("url"),
                    raw=item,
                )
            )
        return pages

    async def crawl(self, url: str, *, max_pages: int = 20) -> list[ExtractedWebPage]:
        return await self.extract([url])

    async def _post_json(self, path: str, payload: dict) -> dict:
        last_error: TavilySearchError | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(f"{self.BASE_URL}{path}", json=payload)
                except httpx.TimeoutException as exc:
                    last_error = TavilySearchError(
                        code="TAVILY_TIMEOUT",
                        message="Tavily request timed out.",
                        retryable=True,
                        reason="timeout",
                    )
                    if attempt >= self.max_retries:
                        raise last_error from exc
                except httpx.ConnectError as exc:
                    last_error = TavilySearchError(
                        code="TAVILY_CONNECTION_ERROR",
                        message="Could not connect to Tavily.",
                        retryable=True,
                        reason="connection_error",
                    )
                    if attempt >= self.max_retries:
                        raise last_error from exc
                else:
                    if response.is_success:
                        try:
                            return response.json()
                        except Exception as exc:
                            raise TavilySearchError(
                                code="TAVILY_RESPONSE_PARSE_ERROR",
                                message="Could not parse Tavily response.",
                                http_status=response.status_code,
                                retryable=False,
                                reason="parse_error",
                            ) from exc

                    body = _safe_json(response)
                    code, message, retryable, reason = classify_tavily_http(response.status_code, body)
                    last_error = TavilySearchError(
                        code=code,
                        message=message,
                        http_status=response.status_code,
                        retryable=retryable,
                        reason=reason,
                    )
                    logger.warning(
                        "tavily_request_failed",
                        path=path,
                        http_status=response.status_code,
                        error_code=code,
                        reason=reason,
                        attempt=attempt + 1,
                    )
                    if not retryable or attempt >= self.max_retries:
                        raise last_error

                delay = min(self.retry_max_seconds, self.retry_base_seconds * (2**attempt))
                delay += random.uniform(0, 0.25)
                await asyncio.sleep(delay)

        if last_error:
            raise last_error
        raise TavilySearchError(code="WEB_SEARCH_UNKNOWN_ERROR", message="Tavily request failed.")


def _normalize_result(item: dict) -> SearchResult | None:
    url = str(item.get("url") or "").strip()[:1000]
    title = str(item.get("title") or url or "Untitled").strip()[:500]
    snippet = str(item.get("content") or item.get("snippet") or "").strip()
    if not url or not title:
        return None
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return SearchResult(
        title=title,
        url=url,
        snippet=snippet[:2000] or None,
        content=snippet[:2000] or None,
        source_domain=host,
        publisher=_guess_publisher(url),
        source_type=_classify_url(url),
        authority_level=_authority_for_url(url),
        retrieved_at=datetime.now(UTC),
        score=item.get("score"),
    )


def _safe_json(response: httpx.Response) -> dict | None:
    try:
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _guess_publisher(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host.split(".")[0].upper() if host else "unknown"


def _classify_url(url: str) -> str:
    from app.search.carrier_registry import CARRIER_DOMAINS, normalize_domain, validate_official_source

    host = normalize_domain(url)
    for carrier, domains in CARRIER_DOMAINS.items():
        if domains and validate_official_source(url, carrier):
            return "official_provider"
    if any(x in host for x in ("fbr.gov", "psw.gov", "gov.pk")):
        return "government"
    if any(x in host for x in ("reddit", "facebook", "twitter", "forum")):
        return "community"
    return "general"


def _authority_for_url(url: str) -> int:
    st = _classify_url(url)
    return {"government": 1, "official_provider": 1, "general": 4, "community": 6}.get(st, 5)
