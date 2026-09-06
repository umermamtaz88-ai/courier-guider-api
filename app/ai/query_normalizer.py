import re

ROMAN_URDU_MAP = {
    "bhejna": "ship",
    "bhejo": "ship",
    "bhej": "ship",
    "parcel": "shipment",
    "kapre": "clothing",
    "kapron": "clothing",
    "kapra": "clothing",
    "order": "order",
    "wapsi": "return",
    "wapas": "return",
    "paisa": "refund",
    "raqam": "amount",
    "track": "tracking",
    "kahan": "where",
    "kitna": "how much",
    "qeemat": "price",
    "sasta": "cheapest",
    "tez": "fastest",
    "rate": "quote",
    "custom": "customs",
    "document": "document",
    "masla": "issue",
    "problem": "issue",
    "deliver": "delivery",
    "ndr": "delivery failed",
    "se": "from",
}


def normalize_query(query: str) -> str:
    """Lightweight Roman Urdu / mixed-language normalization for retrieval."""
    text = query.strip()
    lower = text.lower()
    for urdu, english in ROMAN_URDU_MAP.items():
        lower = re.sub(rf"\b{re.escape(urdu)}\b", english, lower)
    return lower
