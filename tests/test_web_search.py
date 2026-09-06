import pytest

from app.services.web_search.web_search_service import WebSearchService


class _FakeDB:
    pass


def test_needs_web_search_for_current_price():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    assert svc.needs_web_search("What is the current DHL rate?", rag_hit_count=3, rag_freshness="stale")


def test_needs_web_search_when_no_rag():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    assert svc.needs_web_search("Tell me about shipping", rag_hit_count=0)


def test_skip_web_search_when_rag_fresh_general_policy():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    assert not svc.needs_web_search(
        "What is Leopards return policy?",
        rag_hit_count=5,
        rag_freshness="current",
        intent="provider_policy",
    )


def test_web_search_for_shipping_comparison_even_with_recent_rag():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    assert svc.needs_web_search(
        "I want to send clothes packs from Karachi to Lahore which courier is best",
        rag_hit_count=4,
        rag_freshness="recent",
        intent="compare_providers",
    )


def test_web_search_for_shipment_planning():
    svc = WebSearchService(_FakeDB())  # type: ignore[arg-type]
    assert svc.needs_web_search(
        "Ship my parcel to Lahore",
        rag_hit_count=3,
        rag_freshness="current",
        intent="plan_shipment",
    )


@pytest.mark.asyncio
async def test_mock_web_search_provider():
    from app.integrations.web_search.mock import MockWebSearchProvider

    results = await MockWebSearchProvider().search("TCS rate Lahore", domains=["tcsexpress.com"])
    assert results
    assert "DEMO" in results[0].snippet
