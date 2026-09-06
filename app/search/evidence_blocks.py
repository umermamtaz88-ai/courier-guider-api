"""Assemble labeled evidence blocks with [S#] ids for the LLM."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _domain_of(item: dict[str, Any]) -> str:
    domain = item.get("domain") or item.get("source_domain")
    if domain:
        return str(domain)
    url = item.get("url") or ""
    try:
        return urlparse(str(url)).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def assign_source_ids(
    *,
    official_web: list[dict[str, Any]],
    internal_docs: list[dict[str, Any]],
    third_party_web: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stamp stable [S#] ids in precedence order and return flat source list."""
    ordered: list[dict[str, Any]] = []
    n = 1
    for group, tier in (
        (official_web, "official"),
        (internal_docs, "internal_doc"),
        (third_party_web, "third_party"),
    ):
        for raw in group:
            item = dict(raw)
            item["id"] = f"S{n}"
            item["citation_id"] = f"[S{n}]"
            item["tier"] = item.get("tier") or tier
            item["domain"] = item.get("domain") or _domain_of(item)
            ordered.append(item)
            n += 1
    return ordered


def format_evidence_blocks(sources: list[dict[str, Any]]) -> str:
    """Build OFFICIAL_WEB / INTERNAL_DOCS / THIRD_PARTY_WEB markdown for the LLM."""
    official = [s for s in sources if s.get("tier") == "official"]
    internal = [s for s in sources if s.get("tier") == "internal_doc"]
    third = [s for s in sources if s.get("tier") == "third_party"]

    def _chunk(s: dict[str, Any], *, unofficial: bool = False) -> str:
        sid = s.get("citation_id") or f"[{s.get('id', '?')}]"
        title = s.get("title") or "Untitled"
        url = s.get("url") or ""
        carrier = s.get("carrier") or s.get("provider") or ""
        domain = s.get("domain") or _domain_of(s)
        tier = s.get("tier") or ""
        body = (s.get("content") or s.get("snippet") or "")[:900]
        mark = " [UNOFFICIAL]" if unofficial else ""
        return (
            f"{sid}{mark} tier={tier} carrier={carrier or '-'} domain={domain}\n"
            f"source: {title}\nurl: {url}\n{body}"
        )

    sections: list[str] = []
    sections.append("## OFFICIAL_WEB (highest authority for provider facts)")
    if official:
        by_carrier: dict[str, list[dict]] = {}
        for s in official:
            key = str(s.get("carrier") or s.get("provider") or "general")
            by_carrier.setdefault(key, []).append(s)
        for carrier, items in by_carrier.items():
            sections.append(f"### Carrier: {carrier}")
            sections.extend(_chunk(s) for s in items)
    else:
        sections.append("(none)")

    sections.append("## INTERNAL_DOCS")
    if internal:
        sections.extend(_chunk(s) for s in internal)
    else:
        sections.append("(none)")

    sections.append("## THIRD_PARTY_WEB (attribute as third-party; never as carrier policy)")
    if third:
        sections.extend(_chunk(s, unofficial=True) for s in third)
    else:
        sections.append("(none)")

    sections.append(
        "\nSource precedence: (1) current official provider (2) current government "
        "(3) older verified internal doc (4) trusted secondary (5) general third-party "
        "(6) community. Missing official facts → say "
        "'Not currently verified from the official source.' Do not invent."
    )
    return "\n\n".join(sections)
