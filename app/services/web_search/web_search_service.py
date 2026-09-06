"""Decide when web search is needed and run targeted Tavily/mock search."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline_trace import PipelineErrorCode
from app.config import get_settings
from app.db.models import WebSearchResult
from app.integrations.web_search.errors import classify_tavily_exception, classify_web_search_config
from app.integrations.web_search.registry import get_web_search_provider
from app.logging import get_logger

logger = get_logger("courier_guider.web_search")

CURRENTNESS_PATTERNS = re.compile(
    r"\b(current|latest|today|now|recent|updated|this year|price|rate|how much)\b",
    re.I,
)
EXPLICIT_SEARCH = re.compile(r"\b(search the web|look online|google|check online)\b", re.I)
SHIPPING_QUERY = re.compile(
    r"\b(ship|send|courier|parcel|package|pack|lahore|karachi|islamabad|domestic|delivery)\b",
    re.I,
)
LIVE_SHIPPING_INTENTS = frozenset(
    {"compare_providers", "get_shipping_quote", "plan_shipment"}
)


@dataclass
class WebSearchOutcome:
    results: list[dict] = field(default_factory=list)
    provider: str = "unknown"
    requested: bool = False
    error_code: str | None = None
    error_message: str | None = None
    http_status: int | None = None
    domains: list[str] = field(default_factory=list)
    retryable: bool = False


class WebSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    def needs_web_search(
        self,
        message: str,
        *,
        rag_hit_count: int,
        rag_freshness: str | None = None,
        intent: str | None = None,
    ) -> bool:
        if EXPLICIT_SEARCH.search(message):
            return True
        if CURRENTNESS_PATTERNS.search(message):
            return True
        if intent in LIVE_SHIPPING_INTENTS:
            return True
        if SHIPPING_QUERY.search(message) and intent not in ("track_shipment", "shipment_status"):
            return True
        if intent in ("get_shipping_quote", "shipping_estimate") and rag_freshness in (
            None,
            "stale",
            "expired",
            "unknown",
        ):
            return True
        if rag_hit_count == 0:
            return True
        if rag_freshness in ("stale", "expired"):
            return True
        return False

    def build_query(
        self,
        message: str,
        *,
        providers: list[str] | None = None,
        topics: list[str] | None = None,
        country: str = "Pakistan",
    ) -> str:
        parts = [message.strip()]
        if providers:
            parts.append(" ".join(providers))
        if topics:
            parts.append(" ".join(topics[:3]))
        parts.append(country)
        return " ".join(parts)[:400]

    def domains_for_providers(self, providers: list[str] | None) -> list[str] | None:
        from app.search.carrier_registry import domains_for, resolve_carriers

        names = resolve_carriers(" ".join(str(p) for p in (providers or [])))
        cleaned = domains_for(names)
        return cleaned or None

    async def search_for_providers(
        self,
        *,
        tenant_id: uuid.UUID | None,
        message: str,
        providers: list[str],
        topics: list[str] | None = None,
        country: str = "Pakistan",
        max_results_per_provider: int = 2,
        intent: str | None = None,
        request_id: str | None = None,
    ) -> "WebSearchOutcome":
        """
        Official-source-first: one Tavily call per carrier on verified domains only,
        with labeled third-party fallback when official hits are insufficient.
        """
        from app.search.carrier_registry import resolve_carriers
        from app.search.official_search import OfficialWebSearchService
        from app.search.query_plan import QueryPlan, classify_query_plan

        _ = topics, country, max_results_per_provider
        plan = classify_query_plan(message)
        carriers = resolve_carriers(" ".join(str(p) for p in providers)) if providers else list(plan.carriers)
        allowed = {
            "comparison",
            "rates",
            "transit_time",
            "coverage",
            "tracking",
            "policy",
            "general",
        }
        plan_intent = intent if intent in allowed else plan.intent
        plan = QueryPlan(
            intent=plan_intent,  # type: ignore[arg-type]
            carriers=carriers or plan.carriers,
            needs_live_search=True,
        )

        official = OfficialWebSearchService(self.db)
        outcome = await official.search_from_plan(
            tenant_id=tenant_id,
            message=message,
            plan=plan,
            request_id=request_id,
        )
        return WebSearchOutcome(
            results=outcome.results,
            provider=outcome.provider,
            requested=outcome.requested,
            error_code=outcome.error_code,
            error_message=outcome.error_message,
            http_status=outcome.http_status,
            domains=outcome.domains,
            retryable=outcome.retryable,
        )

    async def search(
        self,
        *,
        tenant_id: uuid.UUID | None,
        query: str,
        domains: list[str] | None = None,
        max_results: int | None = None,
    ) -> WebSearchOutcome:
        settings = self.settings
        max_results = max_results or settings.tavily_max_results
        normalized = re.sub(r"\s+", " ", query.lower()).strip()[:500]
        domain_list = domains or []

        configured = (settings.web_search_provider or "mock").lower()
        config_error = classify_web_search_config(
            configured,
            has_tavily_key=bool(settings.tavily_api_key),
            configured_provider=configured,
        )
        if config_error and configured == "tavily":
            return WebSearchOutcome(
                provider=configured,
                requested=True,
                error_code=config_error,
                error_message="Tavily web search is not fully configured",
                domains=domain_list,
            )

        try:
            cached = await self._get_cache(normalized)
            if cached:
                return WebSearchOutcome(
                    results=cached,
                    provider="cache",
                    requested=True,
                    domains=_domains_from_results(cached),
                )
        except Exception as exc:
            logger.warning("web_search_cache_read_failed", error=str(exc)[:200])

        provider = get_web_search_provider()
        provider_name = getattr(provider, "name", "unknown")
        try:
            results = await provider.search(
                query,
                domains=domains,
                max_results=max_results,
                search_depth=settings.tavily_search_depth,
            )
        except Exception as exc:
            error_code, http_status, message = classify_tavily_exception(exc)
            logger.warning(
                "web_search_provider_failed",
                provider=provider_name,
                error_code=error_code,
                http_status=http_status,
            )
            return WebSearchOutcome(
                provider=provider_name,
                requested=True,
                error_code=error_code,
                error_message=message,
                http_status=http_status,
                domains=domain_list,
                retryable=error_code in {
                    PipelineErrorCode.TAVILY_RATE_LIMIT,
                    PipelineErrorCode.TAVILY_TIMEOUT,
                    PipelineErrorCode.TAVILY_CONNECTION_ERROR,
                    PipelineErrorCode.TAVILY_SERVER_ERROR,
                },
            )

        if provider_name == "mock":
            return WebSearchOutcome(
                results=[
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": (r.snippet or "")[:800],
                        "source_type": r.source_type,
                        "authority_level": r.authority_level,
                        "publisher": r.publisher,
                        "freshness": "current",
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "label": "DEMO_SEARCH_RESULT",
                    }
                    for r in results
                ],
                provider=provider_name,
                requested=True,
                error_code=PipelineErrorCode.WEB_SEARCH_NOT_CONFIGURED,
                error_message="Mock web search provider in use; configure WEB_SEARCH_PROVIDER=tavily and TAVILY_API_KEY",
                domains=domain_list or _domains_from_provider_results(results),
            )

        out: list[dict] = []
        expires = datetime.now(UTC) + timedelta(hours=settings.web_search_cache_hours)
        for r in results:
            if hasattr(r, "to_evidence_dict"):
                item = r.to_evidence_dict()
            else:
                if not r.url or not r.title:
                    continue
                item = {
                    "title": r.title[:500],
                    "url": r.url[:1000],
                    "snippet": (r.snippet or "")[:800],
                    "source_type": r.source_type,
                    "authority_level": r.authority_level,
                    "publisher": r.publisher,
                    "freshness": "current",
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "label": "LIVE_SEARCH_RESULT",
                    "source_domain": urlparse(r.url).netloc.lower().removeprefix("www."),
                }
            if not item.get("url") or not item.get("title"):
                continue
            out.append(item)
            try:
                self.db.add(
                    WebSearchResult(
                        tenant_id=tenant_id,
                        query=query,
                        normalized_query=normalized,
                        provider=provider_name,
                        url=item["url"],
                        title=item["title"],
                        snippet=item["snippet"],
                        authority_level=r.authority_level,
                        source_type=r.source_type,
                        expires_at=expires,
                        persisted_to_rag=False,
                    )
                )
            except Exception as exc:
                logger.warning("web_search_cache_write_row_failed", error=str(exc)[:200])

        try:
            await self.db.flush()
        except Exception as exc:
            logger.warning("web_search_cache_flush_failed", error=str(exc)[:200])

        if not out:
            return WebSearchOutcome(
                provider=provider_name,
                requested=True,
                error_code=PipelineErrorCode.TAVILY_EMPTY_RESULTS,
                error_message="No relevant web results were found.",
                domains=domain_list,
            )

        return WebSearchOutcome(
            results=out,
            provider=provider_name,
            requested=True,
            domains=_domains_from_results(out),
        )

    async def _get_cache(self, normalized_query: str) -> list[dict] | None:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(WebSearchResult)
            .where(
                WebSearchResult.normalized_query == normalized_query,
                (WebSearchResult.expires_at.is_(None)) | (WebSearchResult.expires_at >= now),
            )
            .order_by(WebSearchResult.retrieved_at.desc())
            .limit(5)
        )
        rows = list(result.scalars().all())
        if not rows:
            return None
        return [
            {
                "title": r.title,
                "url": r.url,
                "snippet": (r.snippet or "")[:800],
                "source_type": r.source_type,
                "authority_level": r.authority_level,
                "freshness": "recent",
                "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
                "label": "CACHED_SEARCH_RESULT",
            }
            for r in rows
        ]


def freshness_label(effective_from, effective_to, *, max_age_days: int = 90) -> str:
    now = datetime.now(UTC)
    if effective_to and effective_to < now:
        return "expired"
    if effective_from:
        age = (now - effective_from).days
        if age <= 30:
            return "current"
        if age <= max_age_days:
            return "recent"
        return "stale"
    return "unknown"


def _domains_from_results(results: list[dict]) -> list[str]:
    domains: list[str] = []
    for item in results:
        url = item.get("url") or ""
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if host:
            domains.append(host)
    return list(dict.fromkeys(domains))


def _domains_from_provider_results(results) -> list[str]:
    domains: list[str] = []
    for item in results:
        host = urlparse(item.url).netloc.lower().removeprefix("www.")
        if host:
            domains.append(host)
    return list(dict.fromkeys(domains))
