from datetime import UTC, datetime, timedelta

DEFAULT_FREQUENCIES = {
    "provider_pricing": timedelta(days=7),
    "provider_policy": timedelta(days=14),
    "government_rules": timedelta(days=30),
    "general": timedelta(days=90),
}


def is_stale(last_crawled_at: datetime | None, source_type: str) -> bool:
    if last_crawled_at is None:
        return True
    freq = DEFAULT_FREQUENCIES.get(source_type, DEFAULT_FREQUENCIES["general"])
    return datetime.now(UTC) - last_crawled_at > freq
