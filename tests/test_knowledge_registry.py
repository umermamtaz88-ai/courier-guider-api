from app.knowledge.source_registry import SOURCE_REGISTRY


def test_source_registry_has_providers():
    providers = {s["provider"] for s in SOURCE_REGISTRY}
    assert "TCS" in providers
    assert "Leopards" in providers
    assert "DHL" in providers


def test_sources_not_crawl_enabled_by_default():
    assert all(not s.get("crawl_enabled") for s in SOURCE_REGISTRY)
