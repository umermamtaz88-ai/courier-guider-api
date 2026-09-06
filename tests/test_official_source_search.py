"""Official-source-first search: registry, plan, per-carrier Tavily, validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.web_search.models import SearchResult
from app.search.carrier_registry import (
    CARRIER_DOMAINS,
    domains_for,
    normalize_domain,
    resolve_carriers,
    validate_official_source,
)
from app.search.official_search import OfficialWebSearchService
from app.search.query_plan import classify_query_plan


# --- Domain validation ---


def test_official_domain_returns_true():
    assert validate_official_source("https://www.tcsexpress.com/services", "tcs")
    assert validate_official_source("https://sub.leopardscourier.com/x", "leopards")


def test_random_blog_returns_false():
    assert not validate_official_source("https://random-blog.com/tcs-rates", "tcs")


def test_lookalike_malicious_domain_returns_false():
    assert not validate_official_source("https://tcsexpress.com.fake-site.com/x", "tcs")
    assert not validate_official_source("https://not-leopardscourier.com", "leopards")


def test_subdomain_of_approved_domain_ok():
    assert validate_official_source("https://support.dhl.com/pk", "dhl")


def test_url_with_path_query_normalized():
    assert normalize_domain("https://WWW.Blue-Ex.com/path?q=1#frag") == "blue-ex.com"
    assert validate_official_source("https://www.blue-ex.com/rates?city=khi", "blueex")


# --- Carrier resolution ---


def test_resolve_leopards_courier_only():
    assert resolve_carriers("leopards courier") == ["leopards"]


def test_resolve_leopard_alias():
    assert resolve_carriers("Leopard") == ["leopards"]


def test_resolve_tcs_vs_leopards():
    assert resolve_carriers("TCS vs Leopards") == ["tcs", "leopards"]


def test_resolve_case_insensitive():
    assert resolve_carriers("tCs ExPrEsS") == ["tcs"]


def test_resolve_dedupes():
    assert resolve_carriers("TCS and TCS Express") == ["tcs"]


def test_resolve_mnp():
    assert resolve_carriers("m&p courier") == ["m&p"]


def test_kon_behtar_carriers_and_comparison_intent():
    text = "kon behtar hai TCS ya Leopard?"
    assert resolve_carriers(text) == ["tcs", "leopards"]
    plan = classify_query_plan(text)
    assert plan.intent == "comparison"
    assert plan.carriers == ["tcs", "leopards"]


def test_open_comparison_no_required_provider():
    plan = classify_query_plan("Which courier is best for 8kg clothes from Lahore to Karachi?")
    assert plan.intent == "comparison"
    assert plan.carriers == []


def test_compare_tcs_and_leopards_resolves_both():
    plan = classify_query_plan("Compare TCS and Leopards")
    assert plan.intent == "comparison"
    assert plan.carriers == ["tcs", "leopards"]


def test_domains_for_verified_only():
    assert "tcsexpress.com" in domains_for(["tcs"])
    # Unverified carriers must not contribute official domains
    assert domains_for(["daewoo"]) == []


# --- Per-carrier Tavily orchestration ---


def _sr(url: str, title: str = "Page") -> SearchResult:
    return SearchResult(
        title=title,
        url=url,
        content="Service details COD tracking coverage delivery charges for evaluation. " * 3,
        snippet="Service details COD tracking coverage delivery charges.",
        source_domain=normalize_domain(url),
        retrieved_at=datetime.now(UTC),
        source_type="general",
        authority_level=4,
    )


class _RecordingProvider:
    name = "tavily"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def search(
        self,
        query: str,
        *,
        domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
        search_depth: str = "basic",
    ) -> list[SearchResult]:
        self.calls.append(
            {
                "query": query,
                "domains": list(domains or []),
                "exclude_domains": list(exclude_domains or []),
                "max_results": max_results,
                "search_depth": search_depth,
            }
        )
        if domains:
            d0 = domains[0]
            return [
                _sr(f"https://www.{d0}/services", f"{d0} services"),
                _sr(f"https://www.{d0}/cod", f"{d0} COD"),
            ]
        # third-party fallback
        return [_sr("https://news-example.com/courier-review", "Review article")]


@pytest.mark.asyncio
async def test_comparison_one_tavily_call_per_carrier_scoped_domains():
    provider = _RecordingProvider()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    svc = OfficialWebSearchService(db)  # type: ignore[arg-type]
    plan = classify_query_plan("Compare TCS and Leopards delivery")
    with patch("app.search.official_search.get_web_search_provider", return_value=provider):
        with patch("app.search.official_search.classify_web_search_config", return_value=None):
            outcome = await svc.search_from_plan(
                tenant_id=None,
                message="Compare TCS and Leopards delivery",
                plan=plan,
            )

    official_calls = [c for c in provider.calls if c["domains"]]
    assert len(official_calls) == 2
    domain_sets = [set(c["domains"]) for c in official_calls]
    assert {"tcsexpress.com"} in domain_sets
    assert {"leopardscourier.com"} in domain_sets
    for c in official_calls:
        assert c["domains"] == [c["domains"][0]]  # only that carrier
        assert c["search_depth"] == "advanced"
        assert c["max_results"] == 4
        assert "better" not in c["query"].lower()
    assert all(r.get("tier") == "official" for r in outcome.results if r.get("tier") == "official")


@pytest.mark.asyncio
async def test_zero_official_hits_triggers_one_tier2_with_exclude():
    class EmptyThenThird(_RecordingProvider):
        async def search(self, query, *, domains=None, exclude_domains=None, max_results=5, search_depth="basic"):
            self.calls.append(
                {
                    "query": query,
                    "domains": list(domains or []),
                    "exclude_domains": list(exclude_domains or []),
                    "max_results": max_results,
                    "search_depth": search_depth,
                }
            )
            if domains:
                return []  # zero official
            return [_sr("https://blog.example.com/leopards", "Unofficial writeup")]

    provider = EmptyThenThird()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    svc = OfficialWebSearchService(db)  # type: ignore[arg-type]
    plan = classify_query_plan("latest Leopards COD policy")
    with patch("app.search.official_search.get_web_search_provider", return_value=provider):
        with patch("app.search.official_search.classify_web_search_config", return_value=None):
            outcome = await svc.search_from_plan(
                tenant_id=None,
                message="latest Leopards COD policy",
                plan=plan,
            )

    assert len([c for c in provider.calls if c["domains"]]) == 1
    tier2 = [c for c in provider.calls if not c["domains"]]
    assert len(tier2) == 1
    assert "reddit.com" in tier2[0]["exclude_domains"]
    assert outcome.third_party_fallback_count == 1
    assert any(r.get("tier") == "third_party" for r in outcome.results)


@pytest.mark.asyncio
async def test_no_official_tier_outside_registry():
    class BadOfficial(_RecordingProvider):
        async def search(self, query, *, domains=None, exclude_domains=None, max_results=5, search_depth="basic"):
            self.calls.append({"domains": list(domains or []), "exclude_domains": list(exclude_domains or [])})
            # Provider wrongly returns a blog even when include_domains set
            return [_sr("https://medium.com/@x/tcs-tips", "Blog tips")]

    provider = BadOfficial()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    svc = OfficialWebSearchService(db)  # type: ignore[arg-type]
    plan = classify_query_plan("TCS overnight charges Karachi to Lahore")
    with patch("app.search.official_search.get_web_search_provider", return_value=provider):
        with patch("app.search.official_search.classify_web_search_config", return_value=None):
            outcome = await svc.search_from_plan(
                tenant_id=None,
                message="TCS overnight charges Karachi to Lahore",
                plan=plan,
            )

    assert not any(r.get("tier") == "official" for r in outcome.results)


@pytest.mark.asyncio
async def test_single_carrier_does_not_fan_out():
    provider = _RecordingProvider()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    svc = OfficialWebSearchService(db)  # type: ignore[arg-type]
    plan = classify_query_plan("TCS overnight charges Karachi to Lahore")
    assert plan.carriers == ["tcs"]
    with patch("app.search.official_search.get_web_search_provider", return_value=provider):
        with patch("app.search.official_search.classify_web_search_config", return_value=None):
            await svc.search_from_plan(
                tenant_id=None,
                message="TCS overnight charges Karachi to Lahore",
                plan=plan,
            )
    assert len([c for c in provider.calls if c["domains"]]) == 1
    assert provider.calls[0]["domains"] == ["tcsexpress.com"]


@pytest.mark.asyncio
async def test_no_carrier_preserves_generic_behavior():
    provider = _RecordingProvider()
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    svc = OfficialWebSearchService(db)  # type: ignore[arg-type]
    plan = classify_query_plan("What is volumetric weight?")
    assert plan.carriers == []
    with patch("app.search.official_search.get_web_search_provider", return_value=provider):
        with patch("app.search.official_search.classify_web_search_config", return_value=None):
            outcome = await svc.search_from_plan(
                tenant_id=None,
                message="What is volumetric weight?",
                plan=plan,
            )
    # Generic path: single unscoped call
    assert len(provider.calls) == 1
    assert provider.calls[0]["domains"] == []
    assert all(r.get("tier") != "official" or normalize_domain(r.get("url") or "") in {
        d for domains in CARRIER_DOMAINS.values() for d in domains
    } for r in outcome.results)


def test_third_party_and_internal_tiers_stable():
    from app.ai.research_sources import normalize_research_source

    tp = normalize_research_source(
        {
            "title": "Blog",
            "url": "https://blog.example.com/x",
            "tier": "third_party",
            "carrier": "tcs",
            "id": "S2",
        }
    )
    assert tp is not None
    assert tp["tier"] == "third_party"

    doc = normalize_research_source(
        {
            "title": "Internal guide",
            "url": None,
            "tier": "internal_doc",
            "label": "STORED_KNOWLEDGE",
            "id": "S3",
        }
    )
    assert doc is not None
    assert doc["tier"] == "internal_doc"


def test_official_normalize_keeps_official_tier():
    from app.ai.research_sources import normalize_research_source

    src = normalize_research_source(
        {
            "title": "TCS",
            "url": "https://www.tcsexpress.com/x",
            "tier": "official",
            "carrier": "tcs",
            "provider": "TCS",
            "id": "S1",
        }
    )
    assert src is not None
    assert src["tier"] == "official"
    assert src["id"] == "S1"
