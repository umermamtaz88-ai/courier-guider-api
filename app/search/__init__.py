"""Official-source-first live search package."""

from app.search.carrier_registry import (
    BLOCKED_DOMAINS,
    CARRIER_ALIASES,
    CARRIER_DOMAINS,
    CARRIER_OFFICIAL_STATUS,
    DEFAULT_COMPARE_CARRIERS,
    domains_for,
    normalize_domain,
    resolve_carriers,
    validate_official_source,
)
from app.search.query_plan import QueryPlan, classify_query_plan

__all__ = [
    "BLOCKED_DOMAINS",
    "CARRIER_ALIASES",
    "CARRIER_DOMAINS",
    "CARRIER_OFFICIAL_STATUS",
    "DEFAULT_COMPARE_CARRIERS",
    "QueryPlan",
    "classify_query_plan",
    "domains_for",
    "normalize_domain",
    "resolve_carriers",
    "validate_official_source",
]
