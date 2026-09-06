"""Canonical Pakistan courier provider catalog for RAG + web search + citations."""

from __future__ import annotations

# Canonical display name → official site + search domains
PROVIDER_CATALOG: dict[str, dict] = {
    "TCS": {
        "aliases": ["tcs", "tcs express", "tcsexpress"],
        "url": "https://www.tcsexpress.com",
        "domains": ["tcsexpress.com", "www.tcsexpress.com"],
        "publisher": "TCS",
    },
    "Leopards": {
        "aliases": ["leopards", "leopard", "leopards courier", "leopardscourier"],
        "url": "https://www.leopardscourier.com",
        "domains": ["leopardscourier.com", "www.leopardscourier.com"],
        "publisher": "Leopards Courier",
    },
    "DHL": {
        "aliases": ["dhl", "dhl express", "dhl pakistan"],
        "url": "https://www.dhl.com/pk-en/home.html",
        "domains": ["dhl.com", "www.dhl.com"],
        "publisher": "DHL",
    },
    "BlueEx": {
        "aliases": ["blueex", "blue-ex", "blue ex", "bluex"],
        "url": "https://www.blue-ex.com",
        "domains": ["blue-ex.com", "www.blue-ex.com"],
        "publisher": "BlueEx",
    },
    "M&P": {
        "aliases": ["m&p", "mnp", "mulph", "mulphilog", "m and p"],
        "url": "https://www.mulphilog.com",
        "domains": ["mulphilog.com", "www.mulphilog.com"],
        "publisher": "M&P",
    },
    "Trax": {
        "aliases": ["trax", "trax pk"],
        "url": "https://trax.pk",
        "domains": ["trax.pk", "www.trax.pk"],
        "publisher": "Trax",
    },
    "Pakistan Post": {
        "aliases": ["pakistan post", "pakpost", "post office"],
        "url": "https://www.pakpost.gov.pk",
        "domains": ["pakpost.gov.pk", "www.pakpost.gov.pk"],
        "publisher": "Pakistan Post",
    },
}

DEFAULT_COMPARE_PROVIDERS = ["TCS", "Leopards", "BlueEx"]


def canonical_provider_name(raw: str | None) -> str | None:
    if not raw:
        return None
    lower = raw.lower().strip()
    for name, meta in PROVIDER_CATALOG.items():
        if lower == name.lower() or lower in meta["aliases"]:
            return name
        for alias in meta["aliases"]:
            if alias in lower or lower in alias:
                return name
    return None


def normalize_provider_list(providers: list[str] | None) -> list[str]:
    out: list[str] = []
    for p in providers or []:
        name = canonical_provider_name(p)
        if name and name not in out:
            out.append(name)
    return out


def detect_providers_in_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found: list[str] = []
    for name, meta in PROVIDER_CATALOG.items():
        for alias in sorted(meta["aliases"], key=len, reverse=True):
            if alias in lower:
                if name not in found:
                    found.append(name)
                break
    return found


def domains_for_provider(name: str) -> list[str]:
    meta = PROVIDER_CATALOG.get(name) or {}
    return list(meta.get("domains") or [])


def domains_for_providers(providers: list[str] | None) -> list[str] | None:
    names = normalize_provider_list(providers)
    if not names:
        return None
    domains: list[str] = []
    for name in names:
        domains.extend(domains_for_provider(name))
    return list(dict.fromkeys(domains)) or None


def official_url_for(name_or_publisher: str | None) -> str | None:
    name = canonical_provider_name(name_or_publisher)
    if not name:
        return None
    return PROVIDER_CATALOG[name]["url"]


def publisher_for(name: str) -> str:
    meta = PROVIDER_CATALOG.get(name) or {}
    return str(meta.get("publisher") or name)


def infer_provider_from_source(
    *,
    publisher: str | None = None,
    title: str | None = None,
    url: str | None = None,
    domain: str | None = None,
) -> str | None:
    blob = " ".join(filter(None, [publisher, title, url, domain])).lower()
    for name, meta in PROVIDER_CATALOG.items():
        if any(a in blob for a in meta["aliases"]):
            return name
        if any(d.replace("www.", "") in blob for d in meta["domains"]):
            return name
    return None
