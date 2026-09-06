"""Normalized research source objects for citations and UI source cards."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.ai.providers_catalog import (
    detect_providers_in_text,
    infer_provider_from_source,
    official_url_for,
    publisher_for,
)


def resolve_official_url(
    *,
    url: str | None,
    publisher: str | None,
    title: str | None = None,
    domain: str | None = None,
) -> str | None:
    """Prefer real URL; otherwise map known publishers to official websites."""
    if url and str(url).strip().startswith("http"):
        return str(url).strip()
    provider = infer_provider_from_source(
        publisher=publisher, title=title, domain=domain, url=url
    )
    return official_url_for(provider) if provider else None


def normalize_source_type(raw: str | None) -> str:
    value = (raw or "").lower().strip()
    if value in {"official", "official_provider"}:
        return "official"
    if value in {"government", "gov"}:
        return "government"
    if value in {"community", "forum", "social"}:
        return "community"
    if value in {"rag", "knowledge", "stored", "internal_guide"}:
        return "secondary"
    if value in {"user", "upload", "attachment"}:
        return "secondary"
    if value in {"demo"}:
        return "secondary"
    return "secondary"


def relevance_label(score: float | None) -> str:
    if score is None:
        return "medium"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def normalize_research_source(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Build the UI/API source card payload from RAG or web evidence."""
    if not raw or not isinstance(raw, dict):
        return None

    title = str(raw.get("title") or "").strip()
    publisher = raw.get("publisher")
    url = raw.get("url") or raw.get("source_url")
    url = str(url).strip() if url else None
    if not title and not url:
        return None
    if not title:
        title = url or "Untitled source"

    domain = raw.get("domain") or raw.get("source_domain")
    if not domain and url:
        domain = urlparse(url).netloc.lower().removeprefix("www.") or None

    provider = raw.get("provider") or infer_provider_from_source(
        publisher=str(publisher) if publisher else None,
        title=title,
        url=url,
        domain=domain,
    )
    if provider:
        publisher = publisher_for(provider)
        url = url or official_url_for(provider)
    else:
        publisher = publisher or domain or "Unknown"
        url = resolve_official_url(
            url=url, publisher=str(publisher), title=title, domain=domain
        )

    if url and not domain:
        domain = urlparse(url).netloc.lower().removeprefix("www.") or None

    source_type_raw = raw.get("source_type") or raw.get("label") or ""
    source_type = normalize_source_type(str(source_type_raw))
    tier = str(raw.get("tier") or "").lower().strip() or None
    if tier == "official":
        source_type = "official"
    elif tier == "third_party":
        source_type = "secondary"
    elif tier == "internal_doc":
        source_type = "secondary"
    elif str(source_type_raw).lower() == "government":
        source_type = "government"
    elif provider and not tier and source_type == "secondary" and str(source_type_raw).lower() in {
        "official",
        "official_provider",
    }:
        source_type = "official"

    if str(source_type_raw).lower() == "government":
        source_type = "government"

    authority = raw.get("authority_level")
    if authority is None:
        authority = raw.get("authority_score")
    try:
        authority_score = float(authority) if authority is not None else (1.0 if provider else 5.0)
    except (TypeError, ValueError):
        authority_score = 5.0

    score = raw.get("relevance_score")
    if score is None:
        score = raw.get("final_score") or raw.get("score")
    try:
        relevance_score = float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        relevance_score = 0.0

    published_at = raw.get("published_at")
    effective = raw.get("effective_date") or raw.get("effective_from")
    retrieved_at = raw.get("retrieved_at") or datetime.now(UTC).isoformat()
    date_display = effective or published_at or raw.get("date")

    freshness = raw.get("freshness_ui") or raw.get("freshness") or "unknown"
    if freshness in ("current", "recent"):
        freshness_ui = "current"
    elif freshness in ("stale", "expired", "outdated"):
        freshness_ui = "outdated"
    else:
        freshness_ui = "unknown"

    content = raw.get("content") or raw.get("snippet") or raw.get("extracted_content")
    content = str(content)[:2000] if content else None

    return {
        "id": str(raw.get("id") or raw.get("citation_id") or "").removeprefix("[").removesuffix("]") or None,
        "title": title[:500],
        "url": url[:1000] if url else None,
        "domain": domain,
        "publisher": str(publisher)[:255],
        "provider": provider,
        "carrier": raw.get("carrier") or (str(provider).lower() if provider else None),
        "tier": tier
        or (
            "official"
            if source_type == "official"
            else "internal_doc"
            if str(raw.get("label") or "").upper() in {"STORED_KNOWLEDGE", "INTERNAL_DOCS"}
            or source_type_raw.lower() in {"rag", "knowledge", "stored", "internal_guide"}
            else "third_party"
            if source_type in {"community", "secondary"} and raw.get("url")
            else "internal_doc"
            if not raw.get("url")
            else None
        ),
        "source_type": source_type,
        "published_at": published_at,
        "effective_date": effective,
        "retrieved_at": retrieved_at,
        "relevance_score": relevance_score,
        "authority_score": authority_score,
        "authority_level": int(authority_score)
        if authority_score == int(authority_score)
        else authority_score,
        "freshness": freshness_ui,
        "date": str(date_display)[:64] if date_display else None,
        "relevance": relevance_label(relevance_score),
        "page": raw.get("page") or raw.get("page_start"),
        "content": content,
        "label": raw.get("label"),
    }


def normalize_sources(
    items: list[dict[str, Any]] | None, *, limit: int = 8
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items or []:
        normalized = normalize_research_source(item)
        if not normalized:
            continue
        key = (normalized.get("url") or normalized.get("title") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= limit:
            break
    return out


def research_indicator(*, web_search_used: bool, rag_used: bool, source_count: int) -> str:
    if web_search_used and source_count:
        return f"RESEARCHED WEB · {source_count} sources"
    if web_search_used:
        return "RESEARCHED WEB"
    if rag_used and source_count:
        return f"RESEARCH COMPLETE · {source_count} sources"
    if rag_used:
        return "CHECKED KNOWLEDGE BASE"
    return "RESEARCH COMPLETE"


def ensure_inline_citations(answer: str, sources: list[dict[str, Any]]) -> str:
    """
    Attach [S#] markers that match the correct provider sources mentioned in the answer.
    Never cite Leopards for a BlueEx claim (and vice versa).
    """
    if not answer or not sources:
        return answer

    def _cite(i: int, src: dict[str, Any]) -> str:
        sid = src.get("id")
        if sid:
            return f"[{str(sid).removeprefix('[').removesuffix(']')}]" if str(sid).startswith("S") else f"[S{sid}]" if str(sid).isdigit() else f"[{sid}]"
        return f"[S{i}]"

    provider_index: dict[str, str] = {}
    for i, src in enumerate(sources, start=1):
        pname = src.get("provider") or src.get("carrier")
        if pname and str(pname) not in provider_index:
            provider_index[str(pname)] = _cite(i, src)

    if re.search(r"\[S?\d+\]", answer):
        return answer

    mentioned = detect_providers_in_text(answer)
    if mentioned:
        markers = "".join(
            provider_index[p] for p in mentioned if p in provider_index
        )
        if markers:
            return answer.rstrip() + f"\n\n{markers}"
        return answer

    markers = "".join(_cite(i, sources[i - 1]) for i in range(1, min(len(sources), 3) + 1))
    return answer.rstrip() + f"\n\n{markers}"
