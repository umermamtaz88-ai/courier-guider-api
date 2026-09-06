"""Single source of truth for verified carrier official domains.

Only domains with official_domain_status == \"verified\" may produce tier=\"official\".
Unverified carriers may still resolve by name, but must not back official factual claims.
"""

from __future__ import annotations

from urllib.parse import urlparse

# Verified official domains only (from project PROVIDER_CATALOG + known global carriers).
# Domains listed in the product brief but not verified against the carrier's own site
# are omitted here and tracked in CARRIER_OFFICIAL_STATUS as \"unverified\".
CARRIER_DOMAINS: dict[str, list[str]] = {
    "tcs": ["tcsexpress.com"],
    "leopards": ["leopardscourier.com"],
    "m&p": ["mulphilog.com"],
    "pakistan post": ["pakpost.gov.pk"],
    "daewoo": [],  # daewoo.com.pk not verified in-repo — do not use for official claims
    "postex": [],  # postex.pk not verified in-repo
    "trax": ["trax.pk"],
    "blueex": ["blue-ex.com"],
    "callcourier": [],  # callcourier.com.pk not verified in-repo
    "rider": [],  # rider.pk not verified in-repo
    "dhl": ["dhl.com"],
    "fedex": ["fedex.com"],
    "aramex": ["aramex.com"],
}

CARRIER_OFFICIAL_STATUS: dict[str, str] = {
    "tcs": "verified",
    "leopards": "verified",
    "m&p": "verified",
    "pakistan post": "verified",
    "daewoo": "unverified",
    "postex": "unverified",
    "trax": "verified",
    "blueex": "verified",
    "callcourier": "unverified",
    "rider": "unverified",
    "dhl": "verified",
    "fedex": "verified",
    "aramex": "verified",
}

CARRIER_ALIASES: dict[str, str] = {
    "tcs express": "tcs",
    "tcs courier": "tcs",
    "tcsexpress": "tcs",
    "leopard": "leopards",
    "leopards courier": "leopards",
    "leopardscourier": "leopards",
    "lcs": "leopards",
    "mnp": "m&p",
    "m and p": "m&p",
    "mulphilog": "m&p",
    "mulph": "m&p",
    "pak post": "pakistan post",
    "pakpost": "pakistan post",
    "post office": "pakistan post",
    "daewoo express": "daewoo",
    "dhl express": "dhl",
    "dhl pakistan": "dhl",
    "blue-ex": "blueex",
    "blue ex": "blueex",
    "bluex": "blueex",
    "call courier": "callcourier",
    "trax pk": "trax",
    "fedex express": "fedex",
}

BLOCKED_DOMAINS: list[str] = [
    "pinterest.com",
    "quora.com",
    "reddit.com",
    "medium.com",
    "slideshare.net",
    "scribd.com",
    "olx.com.pk",
]

# Display names for UI / prompts
CARRIER_DISPLAY: dict[str, str] = {
    "tcs": "TCS",
    "leopards": "Leopards",
    "m&p": "M&P",
    "pakistan post": "Pakistan Post",
    "daewoo": "Daewoo",
    "postex": "PostEx",
    "trax": "Trax",
    "blueex": "BlueEx",
    "callcourier": "CallCourier",
    "rider": "Rider",
    "dhl": "DHL",
    "fedex": "FedEx",
    "aramex": "Aramex",
}

DEFAULT_COMPARE_CARRIERS: list[str] = ["tcs", "leopards", "blueex"]


def normalize_domain(url_or_hostname: str | None) -> str:
    """Normalize a URL or hostname to a bare lowercase hostname without www."""
    raw = (url_or_hostname or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or parsed.netloc or "").lower()
    if not host and "/" in (url_or_hostname or ""):
        host = (url_or_hostname or "").split("/", 1)[0].lower()
    if host.startswith("www."):
        host = host[4:]
    # Drop trailing dots
    return host.rstrip(".")


def _host_matches_approved(host: str, approved: str) -> bool:
    """True if host is approved domain or a real subdomain (not lookalike)."""
    host = normalize_domain(host)
    approved = normalize_domain(approved)
    if not host or not approved:
        return False
    return host == approved or host.endswith("." + approved)


def validate_official_source(url: str, carrier: str) -> bool:
    """Return True only when URL hostname is an approved *verified* domain for carrier."""
    carrier_key = (carrier or "").strip().lower()
    if CARRIER_OFFICIAL_STATUS.get(carrier_key) != "verified":
        return False
    approved = CARRIER_DOMAINS.get(carrier_key) or []
    if not approved:
        return False
    host = normalize_domain(url)
    if not host:
        return False
    return any(_host_matches_approved(host, d) for d in approved)


def is_blocked_domain(url_or_hostname: str) -> bool:
    host = normalize_domain(url_or_hostname)
    if not host:
        return False
    return any(_host_matches_approved(host, blocked) for blocked in BLOCKED_DOMAINS)


def official_domain_status(carrier: str) -> str:
    return CARRIER_OFFICIAL_STATUS.get((carrier or "").strip().lower(), "unverified")


def domains_for(carriers: list[str] | None) -> list[str]:
    """Return verified official domains only for the given carriers."""
    out: list[str] = []
    for carrier in carriers or []:
        key = carrier.strip().lower()
        if official_domain_status(key) != "verified":
            continue
        for domain in CARRIER_DOMAINS.get(key) or []:
            if domain and domain not in out:
                out.append(domain)
    return out


def display_name(carrier: str) -> str:
    key = (carrier or "").strip().lower()
    return CARRIER_DISPLAY.get(key, carrier)


def resolve_carriers(text: str) -> list[str]:
    """
    Case-insensitive, alias-aware carrier resolution.
    Longest match first so \"leopards courier\" → [\"leopards\"] only.
    Deterministic order = order of first appearance in text.
    """
    lower = (text or "").lower()
    if not lower.strip():
        return []

    # Build match terms: aliases + canonical keys, longest first
    terms: list[tuple[str, str]] = []
    for alias, canonical in CARRIER_ALIASES.items():
        terms.append((alias.lower(), canonical))
    for canonical in CARRIER_DOMAINS:
        terms.append((canonical.lower(), canonical))
    terms.sort(key=lambda t: len(t[0]), reverse=True)

    found_spans: list[tuple[int, int, str]] = []
    occupied: list[tuple[int, int]] = []

    for term, canonical in terms:
        start = 0
        while True:
            idx = lower.find(term, start)
            if idx < 0:
                break
            end = idx + len(term)
            # Word-boundary-ish: avoid matching inside longer alnum tokens for short aliases
            before_ok = idx == 0 or not lower[idx - 1].isalnum()
            after_ok = end >= len(lower) or not lower[end].isalnum()
            # Allow & in m&p
            if term == "m&p":
                before_ok = idx == 0 or not lower[idx - 1].isalnum()
                after_ok = end >= len(lower) or not lower[end].isalnum()
            if before_ok and after_ok:
                overlap = any(not (end <= a or idx >= b) for a, b in occupied)
                if not overlap:
                    found_spans.append((idx, end, canonical))
                    occupied.append((idx, end))
            start = idx + 1

    found_spans.sort(key=lambda s: s[0])
    out: list[str] = []
    for _, _, canonical in found_spans:
        if canonical not in out:
            out.append(canonical)
    return out
