"""Per-carrier official-domain Tavily search with labeled third-party fallback."""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import WebSearchResult
from app.integrations.web_search.errors import classify_tavily_exception, classify_web_search_config
from app.integrations.web_search.registry import get_web_search_provider
from app.logging import get_logger
from app.search.carrier_registry import (
    BLOCKED_DOMAINS,
    DEFAULT_COMPARE_CARRIERS,
    display_name,
    domains_for,
    is_blocked_domain,
    normalize_domain,
    official_domain_status,
    validate_official_source,
)
from app.search.query_plan import QueryIntent, QueryPlan, build_carrier_subquery

logger = get_logger("courier_guider.official_search")


@dataclass
class OfficialSearchOutcome:
    results: list[dict] = field(default_factory=list)
    provider: str = "unknown"
    requested: bool = False
    error_code: str | None = None
    error_message: str | None = None
    http_status: int | None = None
    domains: list[str] = field(default_factory=list)
    retryable: bool = False
    official_counts: dict[str, int] = field(default_factory=dict)
    third_party_fallback_count: int = 0
    validation_failures: int = 0
    intent: str | None = None
    carriers: list[str] = field(default_factory=list)


def _normalize_url_key(url: str) -> str:
    raw = (url or "").strip().lower()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = (parsed.path or "/").rstrip("/") or "/"
    return f"{host}{path}"


def _is_homepage_only(url: str, content: str | None) -> bool:
    parsed = urlparse(url or "")
    path = (parsed.path or "").rstrip("/")
    if path not in {"", "/", "/home", "/index", "/index.html", "/pk-en/home.html"}:
        return False
    body = (content or "").strip()
    return len(body) < 120


def _usable_official_hits(hits: list[dict]) -> list[dict]:
    usable = []
    for h in hits:
        if h.get("tier") != "official":
            continue
        url = h.get("url") or ""
        content = h.get("content") or h.get("snippet") or ""
        if not content.strip():
            continue
        if _is_homepage_only(url, content):
            continue
        usable.append(h)
    return usable


class OfficialWebSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def search_from_plan(
        self,
        *,
        tenant_id: uuid.UUID | None,
        message: str,
        plan: QueryPlan,
        request_id: str | None = None,
    ) -> OfficialSearchOutcome:
        carriers = list(plan.carriers)
        if plan.intent == "comparison" and not carriers:
            carriers = list(DEFAULT_COMPARE_CARRIERS)

        if not carriers:
            # Generic behavior — single unscoped search (existing path)
            return await self._generic_search(tenant_id=tenant_id, message=message, plan=plan)

        # Single-carrier factual: one official-domain search only (plus fallback if needed)
        # Multi-carrier / comparison: one official call per carrier
        return await self._per_carrier_search(
            tenant_id=tenant_id,
            message=message,
            plan=plan,
            carriers=carriers,
            request_id=request_id,
        )

    async def _per_carrier_search(
        self,
        *,
        tenant_id: uuid.UUID | None,
        message: str,
        plan: QueryPlan,
        carriers: list[str],
        request_id: str | None,
    ) -> OfficialSearchOutcome:
        settings = self.settings
        timeout = settings.official_search_timeout_seconds
        max_results = settings.official_search_max_results
        depth = settings.official_search_depth
        min_official = settings.official_min_usable_hits
        cap = settings.live_search_result_cap

        logger.info(
            "official_search_start",
            request_id=request_id,
            query=message[:120],
            intent=plan.intent,
            carriers=carriers,
        )

        async def _one_carrier(carrier: str) -> tuple[str, list[dict], int]:
            domains = domains_for([carrier])
            if not domains:
                logger.info(
                    "official_search_skip_unverified",
                    request_id=request_id,
                    carrier=carrier,
                    status=official_domain_status(carrier),
                )
                return carrier, [], 0

            sub_q = build_carrier_subquery(carrier, plan.intent, message)
            hits, failures = await self._scoped_search(
                tenant_id=tenant_id,
                query=sub_q,
                carrier=carrier,
                tier="official",
                include_domains=domains,
                exclude_domains=None,
                max_results=max_results,
                search_depth=depth,
                timeout=timeout,
            )
            return carrier, hits, failures

        gathered = await asyncio.gather(
            *[_one_carrier(c) for c in carriers],
            return_exceptions=True,
        )

        official_by_carrier: dict[str, list[dict]] = {c: [] for c in carriers}
        validation_failures = 0
        for carrier, result in zip(carriers, gathered):
            if isinstance(result, Exception):
                logger.warning(
                    "official_search_carrier_failed",
                    request_id=request_id,
                    carrier=carrier,
                    error=str(result)[:200],
                )
                continue
            c, hits, fails = result
            official_by_carrier[c] = hits
            validation_failures += fails

        # Tier-2 fallback when fewer than min usable official hits
        third_party: list[dict] = []
        third_party_triggers = 0
        for carrier in carriers:
            usable = _usable_official_hits(official_by_carrier.get(carrier) or [])
            if len(usable) >= min_official:
                continue
            third_party_triggers += 1
            logger.info(
                "official_search_tier2_trigger",
                request_id=request_id,
                carrier=carrier,
                official_usable=len(usable),
            )
            sub_q = build_carrier_subquery(carrier, plan.intent, message)
            fallback_hits, fails = await self._scoped_search(
                tenant_id=tenant_id,
                query=sub_q,
                carrier=carrier,
                tier="third_party",
                include_domains=None,
                exclude_domains=list(BLOCKED_DOMAINS),
                max_results=max_results,
                search_depth=depth,
                timeout=timeout,
            )
            validation_failures += fails
            third_party.extend(fallback_hits)

        merged: list[dict] = []
        official_counts: dict[str, int] = {}
        for carrier, hits in official_by_carrier.items():
            official_counts[carrier] = len(hits)
            merged.extend(hits)
        merged.extend(third_party)

        merged = self._dedupe_cap(merged, cap=cap)
        domains_all = list(
            dict.fromkeys(
                normalize_domain(h.get("url") or h.get("domain") or "")
                for h in merged
                if h.get("url") or h.get("domain")
            )
        )

        logger.info(
            "official_search_complete",
            request_id=request_id,
            intent=plan.intent,
            carriers=carriers,
            official_counts=official_counts,
            third_party_fallback_count=third_party_triggers,
            validation_failures=validation_failures,
            final_source_count=len(merged),
        )

        return OfficialSearchOutcome(
            results=merged,
            provider=settings.web_search_provider,
            requested=True,
            domains=domains_all,
            official_counts=official_counts,
            third_party_fallback_count=third_party_triggers,
            validation_failures=validation_failures,
            intent=plan.intent,
            carriers=carriers,
            error_code=None if merged else "TAVILY_EMPTY_RESULTS",
            error_message=None if merged else "No relevant web results were found.",
        )

    async def _generic_search(
        self,
        *,
        tenant_id: uuid.UUID | None,
        message: str,
        plan: QueryPlan,
    ) -> OfficialSearchOutcome:
        settings = self.settings
        hits, fails = await self._scoped_search(
            tenant_id=tenant_id,
            query=message[:400],
            carrier=None,
            tier="third_party",
            include_domains=None,
            exclude_domains=list(BLOCKED_DOMAINS),
            max_results=settings.tavily_max_results,
            search_depth=settings.tavily_search_depth,
            timeout=settings.official_search_timeout_seconds,
        )
        # Re-tag any accidental official matches from known domains
        for h in hits:
            carrier = h.get("carrier")
            url = h.get("url") or ""
            if carrier and validate_official_source(url, carrier):
                h["tier"] = "official"
            else:
                h["tier"] = "third_party"
        hits = self._dedupe_cap(hits, cap=settings.live_search_result_cap)
        return OfficialSearchOutcome(
            results=hits,
            provider=settings.web_search_provider,
            requested=True,
            domains=[normalize_domain(h.get("url") or "") for h in hits if h.get("url")],
            validation_failures=fails,
            intent=plan.intent,
            carriers=[],
        )

    async def _scoped_search(
        self,
        *,
        tenant_id: uuid.UUID | None,
        query: str,
        carrier: str | None,
        tier: str,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
        max_results: int,
        search_depth: str,
        timeout: float,
    ) -> tuple[list[dict], int]:
        settings = self.settings
        normalized = self._cache_key(query, carrier, tier)

        configured = (settings.web_search_provider or "mock").lower()
        config_error = classify_web_search_config(
            configured,
            has_tavily_key=bool(settings.tavily_api_key),
            configured_provider=configured,
        )
        if config_error and configured == "tavily":
            return [], 0

        try:
            cached = await self._get_cache(normalized)
            if cached is not None:
                tagged = []
                for item in cached:
                    row = dict(item)
                    row["carrier"] = carrier
                    row["tier"] = tier
                    row["domain"] = normalize_domain(row.get("url") or row.get("domain") or "")
                    if tier == "official" and carrier:
                        if not validate_official_source(row.get("url") or "", carrier):
                            continue
                    if tier == "third_party" and is_blocked_domain(row.get("url") or ""):
                        continue
                    tagged.append(row)
                return tagged, 0
        except Exception as exc:
            logger.warning("official_search_cache_read_failed", error=str(exc)[:200])

        provider = get_web_search_provider()
        try:
            results = await asyncio.wait_for(
                provider.search(
                    query,
                    domains=include_domains,
                    exclude_domains=exclude_domains,
                    max_results=max_results,
                    search_depth=search_depth,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("official_search_timeout", carrier=carrier, tier=tier, query=query[:80])
            return [], 0
        except TypeError:
            # Provider may not accept exclude_domains yet
            try:
                results = await asyncio.wait_for(
                    provider.search(
                        query,
                        domains=include_domains,
                        max_results=max_results,
                        search_depth=search_depth,
                    ),
                    timeout=timeout,
                )
            except Exception as exc:
                classify_tavily_exception(exc)
                return [], 0
        except Exception as exc:
            classify_tavily_exception(exc)
            return [], 0

        out: list[dict] = []
        failures = 0
        expires = datetime.now(UTC) + timedelta(hours=settings.web_search_cache_hours)
        for r in results or []:
            if hasattr(r, "to_evidence_dict"):
                item = r.to_evidence_dict()
            else:
                url = getattr(r, "url", "") or ""
                item = {
                    "title": getattr(r, "title", "") or url,
                    "url": url,
                    "snippet": (getattr(r, "snippet", None) or getattr(r, "content", None) or "")[:800],
                    "source_domain": normalize_domain(url),
                }
            url = item.get("url") or ""
            domain = normalize_domain(url or item.get("source_domain") or "")
            item["domain"] = domain
            item["carrier"] = carrier
            item["provider"] = display_name(carrier) if carrier else item.get("provider")
            item["publisher"] = display_name(carrier) if carrier else item.get("publisher") or domain

            if tier == "official":
                if not carrier or not validate_official_source(url, carrier):
                    failures += 1
                    logger.info(
                        "source_validation_failure",
                        carrier=carrier,
                        url=url[:200],
                        domain=domain,
                    )
                    continue
                item["tier"] = "official"
                item["source_type"] = "official_provider"
                item["authority_level"] = 1
                item["label"] = "OFFICIAL_WEB"
            else:
                if is_blocked_domain(url):
                    failures += 1
                    continue
                # Hard rule: never promote non-registry domains to official
                if carrier and validate_official_source(url, carrier):
                    item["tier"] = "official"
                    item["source_type"] = "official_provider"
                    item["authority_level"] = 1
                    item["label"] = "OFFICIAL_WEB"
                else:
                    item["tier"] = "third_party"
                    item["source_type"] = "secondary"
                    item["authority_level"] = 5
                    item["label"] = "THIRD_PARTY_WEB"

            out.append(item)
            try:
                self.db.add(
                    WebSearchResult(
                        tenant_id=tenant_id,
                        query=query,
                        normalized_query=normalized,
                        provider=getattr(provider, "name", "unknown"),
                        url=item["url"],
                        title=item.get("title") or item["url"],
                        snippet=item.get("snippet"),
                        authority_level=int(item.get("authority_level") or 5),
                        source_type=str(item.get("source_type") or "general"),
                        expires_at=expires,
                        persisted_to_rag=False,
                    )
                )
            except Exception as exc:
                logger.warning("official_search_cache_write_failed", error=str(exc)[:200])

        try:
            await self.db.flush()
        except Exception as exc:
            logger.warning("official_search_cache_flush_failed", error=str(exc)[:200])

        return out, failures

    def _cache_key(self, query: str, carrier: str | None, tier: str) -> str:
        q = re.sub(r"\s+", " ", (query or "").lower()).strip()[:400]
        return f"{q}|{carrier or '-'}|{tier}"[:500]

    async def _get_cache(self, normalized_query: str) -> list[dict] | None:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(WebSearchResult)
            .where(
                WebSearchResult.normalized_query == normalized_query,
                (WebSearchResult.expires_at.is_(None)) | (WebSearchResult.expires_at >= now),
            )
            .order_by(WebSearchResult.retrieved_at.desc())
            .limit(8)
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
                "domain": normalize_domain(r.url),
            }
            for r in rows
        ]

    @staticmethod
    def _dedupe_cap(items: list[dict], *, cap: int) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []
        # Prefer official over third_party when same URL
        ordered = sorted(
            items,
            key=lambda x: 0 if x.get("tier") == "official" else 1,
        )
        for item in ordered:
            key = _normalize_url_key(item.get("url") or "") or (item.get("title") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= cap:
                break
        return out
