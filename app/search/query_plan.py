"""Keyword/regex-first query plan for official-source live search."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.search.carrier_registry import resolve_carriers


QueryIntent = Literal[
    "comparison",
    "rates",
    "transit_time",
    "coverage",
    "tracking",
    "policy",
    "general",
]


class QueryPlan(BaseModel):
    intent: QueryIntent = "general"
    carriers: list[str] = Field(default_factory=list)
    needs_live_search: bool = False


COMPARISON_RE = re.compile(
    r"\b(better|best|vs|versus|compare|comparison|difference between|which one|kon behtar|acha)\b",
    re.I,
)
RATES_RE = re.compile(
    r"\b(rate|rates|price|pricing|charges|cost|fare|tariff|how much|kitna)\b",
    re.I,
)
TRANSIT_RE = re.compile(
    r"\b(transit|delivery time|how long|eta|overnight|same day|express delivery)\b",
    re.I,
)
COVERAGE_RE = re.compile(
    r"\b(coverage|service area|cities|rural|deliver to|serviceable)\b",
    re.I,
)
TRACKING_RE = re.compile(
    r"\b(track|tracking|where is my|shipment status|awb|cn number)\b",
    re.I,
)
POLICY_RE = re.compile(
    r"\b(policy|cod|cash on delivery|return|refund|claim|insurance|terms)\b",
    re.I,
)
CURRENTNESS_RE = re.compile(
    r"\b(current|latest|today|now|recent|updated|this year|live|search the web|look online)\b",
    re.I,
)
SHIPPING_RE = re.compile(
    r"\b(ship|send|courier|parcel|package|pack|lahore|karachi|islamabad|domestic|delivery)\b",
    re.I,
)


def classify_query_plan(
    text: str,
    *,
    rag_hit_count: int = 0,
    rag_freshness: str | None = None,
    force_live: bool = False,
) -> QueryPlan:
    """Keyword/regex classifier. Carriers may be empty for open comparisons."""
    carriers = resolve_carriers(text)
    intent: QueryIntent = "general"

    if COMPARISON_RE.search(text or ""):
        intent = "comparison"
    elif TRACKING_RE.search(text or ""):
        intent = "tracking"
    elif RATES_RE.search(text or ""):
        intent = "rates"
    elif TRANSIT_RE.search(text or ""):
        intent = "transit_time"
    elif COVERAGE_RE.search(text or ""):
        intent = "coverage"
    elif POLICY_RE.search(text or ""):
        intent = "policy"

    # Named multi-carrier + comparison language → comparison
    if len(carriers) >= 2 and COMPARISON_RE.search(text or ""):
        intent = "comparison"

    needs_live = False
    if force_live:
        needs_live = True
    elif CURRENTNESS_RE.search(text or ""):
        needs_live = True
    elif intent in {"comparison", "rates", "transit_time", "coverage"}:
        needs_live = True
    elif intent == "policy" and CURRENTNESS_RE.search(text or ""):
        needs_live = True
    elif rag_hit_count == 0 and SHIPPING_RE.search(text or ""):
        needs_live = True
    elif rag_freshness in {"stale", "expired"}:
        needs_live = True
    elif carriers and rag_hit_count < max(1, len(carriers)):
        needs_live = True

    # Pure glossary / definition without currentness → prefer RAG
    if intent == "policy" and not CURRENTNESS_RE.search(text or "") and rag_hit_count > 0:
        if not carriers:
            needs_live = False

    return QueryPlan(intent=intent, carriers=carriers, needs_live_search=needs_live)


def build_carrier_subquery(carrier: str, intent: QueryIntent, original: str) -> str:
    """Rewrite comparison/raw opinion text into factual single-carrier search queries."""
    from app.search.carrier_registry import display_name

    name = display_name(carrier)
    topic = {
        "comparison": "delivery time coverage charges services COD tracking",
        "rates": "charges rates pricing tariff COD",
        "transit_time": "delivery time transit overnight express",
        "coverage": "coverage service area cities rural delivery",
        "tracking": "tracking shipment track and trace",
        "policy": "COD policy returns claims terms",
        "general": "services COD tracking delivery",
    }.get(intent, "services COD tracking delivery")
    # Never send raw "which is better" into a single-carrier search
    return f"{name} {topic} Pakistan official"[:400]
