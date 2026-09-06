import re


CITY_ALIASES = {
    "lhr": "Lahore",
    "lahore": "Lahore",
    "khi": "Karachi",
    "karachi": "Karachi",
    "isb": "Islamabad",
    "islamabad": "Islamabad",
    "dha": "DHA",
    "defence": "Defence",
    "defense": "Defence",
}

PROVINCE_PATTERNS = {
    "punjab": "Punjab",
    "sindh": "Sindh",
    "kpk": "KPK",
    "balochistan": "Balochistan",
}


def normalize_address(raw: str) -> dict:
    """Rule-based address normalization without inventing coordinates."""
    text = raw.strip()
    lower = text.lower()

    city = None
    province = None
    for alias, canonical in CITY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            city = canonical if canonical != "DHA" else city
            if canonical in ("Lahore", "Karachi", "Islamabad"):
                city = canonical

    for pat, prov in PROVINCE_PATTERNS.items():
        if pat in lower:
            province = prov

    country = "Pakistan" if not any(x in lower for x in ("uae", "dubai", "usa")) else None
    if "dubai" in lower or "uae" in lower:
        city = city or "Dubai"
        country = "UAE"

    normalized_parts = [p for p in [city, province, country] if p]
    return {
        "raw_address": raw,
        "normalized_address": ", ".join(normalized_parts) if normalized_parts else text,
        "city": city,
        "province": province,
        "country": country or "Pakistan",
        "validation_status": "normalized" if normalized_parts else "unvalidated",
        "validation_source": "rule_based",
        "confidence": 0.7 if normalized_parts else 0.3,
    }
