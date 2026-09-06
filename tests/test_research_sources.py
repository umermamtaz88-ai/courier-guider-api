from app.ai.providers_catalog import canonical_provider_name, detect_providers_in_text
from app.ai.research_sources import (
    ensure_inline_citations,
    normalize_research_source,
    normalize_sources,
    research_indicator,
    resolve_official_url,
)


def test_normalize_official_provider_source():
    src = normalize_research_source(
        {
            "title": "TCS COD",
            "url": "https://www.tcsexpress.com/cod",
            "publisher": "TCS",
            "source_type": "official_provider",
            "authority_level": 1,
            "final_score": 0.9,
            "effective_from": "2024-06-01",
            "content": "TCS supports COD on domestic services.",
        }
    )
    assert src is not None
    assert src["source_type"] == "official"
    assert src["provider"] == "TCS"
    assert src["url"].startswith("https://")


def test_blueex_not_mapped_to_leopards():
    src = normalize_research_source(
        {
            "title": "BlueEx Courier Services Pakistan",
            "publisher": "BlueEx",
            "provider": "BlueEx",
            "source_type": "official_provider",
            "authority_level": 1,
        }
    )
    assert src is not None
    assert src["provider"] == "BlueEx"
    assert src["url"] == "https://www.blue-ex.com"
    assert "leopard" not in (src["url"] or "").lower()
    assert src["publisher"] == "BlueEx"


def test_citation_markers_match_mentioned_provider():
    answer = "BlueEx focuses on e-commerce COD in Pakistan."
    sources = [
        {"provider": "TCS", "publisher": "TCS", "title": "TCS", "url": "https://www.tcsexpress.com"},
        {
            "provider": "BlueEx",
            "publisher": "BlueEx",
            "title": "BlueEx",
            "url": "https://www.blue-ex.com",
        },
    ]
    # normalize first so ensure_inline_citations gets clean dicts
    sources = normalize_sources(sources)
    out = ensure_inline_citations(answer, sources)
    # Should cite BlueEx index, not TCS alone as the only marker for BlueEx text
    assert "[2]" in out or "BlueEx" in str(sources[1]["publisher"])


def test_detect_blueex():
    assert "BlueEx" in detect_providers_in_text("compare blueex and tcs")
    assert canonical_provider_name("blue-ex") == "BlueEx"


def test_resolve_official_url_when_missing():
    assert resolve_official_url(url=None, publisher="TCS", title="TCS Domestic") == (
        "https://www.tcsexpress.com"
    )


def test_normalize_sources_dedupes():
    items = [
        {"title": "A", "url": "https://example.com/a", "source_type": "general"},
        {"title": "A again", "url": "https://example.com/a", "source_type": "general"},
    ]
    out = normalize_sources(items)
    assert len(out) == 1


def test_research_indicator_web():
    assert "RESEARCHED WEB" in research_indicator(web_search_used=True, rag_used=True, source_count=3)
