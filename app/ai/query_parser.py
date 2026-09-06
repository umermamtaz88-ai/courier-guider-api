import re
from dataclasses import dataclass, field

PAKISTAN_CITIES = {
    "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "multan",
    "peshawar", "quetta", "sialkot", "hyderabad", "gujranwala",
}
INTERNATIONAL = {"dubai", "uae", "usa", "uk", "london", "china", "saudi"}
PROVIDERS = {"tcs", "leopards", "dhl", "m&p", "trax", "blueex", "blue-ex", "fedex", "ups", "pakistan post"}
PROBLEM_TERMS = {
    "delayed": "parcel_delayed",
    "refused": "customer_refused",
    "lost": "parcel_lost",
    "damaged": "parcel_damaged",
    "overweight": "overweight",
    "prohibited": "prohibited_item",
    "customs": "customs_issue",
    "tracking stopped": "tracking_stopped",
}


@dataclass
class ParsedQuery:
    intent: str = "general_answer"
    product: str | None = None
    weight_kg: float | None = None
    weight_unit: str = "kg"
    origin: str | None = None
    destination: str | None = None
    country: str = "Pakistan"
    domestic: bool | None = None
    international: bool | None = None
    cod: bool | None = None
    priority: str = "balanced"
    providers: list[str] = field(default_factory=list)
    problem_type: str | None = None
    topics: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)

    def merge(self, other: dict) -> "ParsedQuery":
        for key, value in other.items():
            if value is not None and getattr(self, key, None) in (None, [], ""):
                setattr(self, key, value)
        return self

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "product": self.product,
            "weight": {"value": self.weight_kg, "unit": self.weight_unit} if self.weight_kg else None,
            "origin": self.origin,
            "destination": self.destination,
            "country": self.country,
            "domestic": self.domestic,
            "international": self.international,
            "cod": self.cod,
            "priority": self.priority,
            "providers": self.providers,
            "problem_type": self.problem_type,
            "topics": self.topics,
            "missing_fields": self.missing_fields,
        }


def parse_query(message: str, *, intent: str) -> ParsedQuery:
    lower = message.lower()
    parsed = ParsedQuery(intent=_map_intent(intent))

    if m := re.search(r"\b(\d+(?:\.\d+)?)\s*kg\b", lower):
        parsed.weight_kg = float(m.group(1))

    if re.search(r"\bcloth(?:ing|es)?\b", lower):
        parsed.product = "clothing"
    elif re.search(r"\belectronics?\b", lower):
        parsed.product = "electronics"
    elif re.search(r"\bdocuments?\b", lower):
        parsed.product = "documents"

    for city in PAKISTAN_CITIES:
        if re.search(rf"\b{re.escape(city)}\b", lower):
            if parsed.origin is None and re.search(rf"\bfrom\s+{re.escape(city)}\b", lower):
                parsed.origin = city.title()
            elif parsed.destination is None and re.search(rf"\bto\s+{re.escape(city)}\b", lower):
                parsed.destination = city.title()
            elif parsed.origin is None:
                parsed.origin = city.title()
            elif parsed.destination is None and city.title() != parsed.origin:
                parsed.destination = city.title()

    for dest in INTERNATIONAL:
        if re.search(rf"\bto\s+{re.escape(dest)}\b", lower) or re.search(rf"\b{re.escape(dest)}\b", lower):
            parsed.destination = dest.upper() if dest in ("uae", "usa", "uk") else dest.title()
            parsed.international = True
            parsed.domestic = False

    if parsed.international is None:
        if parsed.origin and parsed.destination:
            parsed.domestic = (
                parsed.origin.lower() in PAKISTAN_CITIES
                and parsed.destination.lower() in PAKISTAN_CITIES
            )
            parsed.international = not parsed.domestic
        elif re.search(r"\b(domestic|local|within pakistan|in pakistan)\b", lower):
            parsed.domestic = True
            parsed.international = False

    if re.search(r"\b(cod|cash on delivery)\b", lower):
        parsed.cod = True
    elif re.search(r"\bprepaid\b", lower):
        parsed.cod = False

    if re.search(r"\b(cheapest|low cost|lowest price)\b", lower):
        parsed.priority = "cheapest"
    elif re.search(r"\b(fastest|quick|urgent|express)\b", lower):
        parsed.priority = "fastest"

    for provider in PROVIDERS:
        if re.search(rf"\b{re.escape(provider)}\b", lower):
            from app.ai.providers_catalog import canonical_provider_name

            name = canonical_provider_name(provider)
            if name and name not in parsed.providers:
                parsed.providers.append(name)

    for term, problem in PROBLEM_TERMS.items():
        if term in lower:
            parsed.problem_type = problem

    for topic in ("return", "refund", "claim", "cod", "customs", "document", "tracking", "price"):
        if re.search(rf"\b{topic}\w*\b", lower):
            parsed.topics.append(topic)

    _fill_missing(parsed)
    return parsed


def _map_intent(intent: str) -> str:
    mapping = {
        "compare_providers": "provider_comparison",
        "get_shipping_quote": "shipping_estimate",
        "required_documents": "documentation_checklist",
        "provider_policy": "policy_explanation",
        "return": "policy_explanation",
        "refund": "policy_explanation",
        "claim": "policy_explanation",
        "cod_settlement": "policy_explanation",
        "explain_issue": "problem_resolution",
        "delivery_failure": "problem_resolution",
        "shipment_delay": "problem_resolution",
    }
    return mapping.get(intent, "general_answer")


def _fill_missing(parsed: ParsedQuery) -> None:
    if parsed.intent == "provider_comparison":
        if not parsed.origin:
            parsed.missing_fields.append("origin")
        if not parsed.destination:
            parsed.missing_fields.append("destination")
        if not parsed.weight_kg:
            parsed.missing_fields.append("weight")
