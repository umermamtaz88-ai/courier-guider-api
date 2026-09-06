import uuid

from app.ai.query_parser import ParsedQuery
from app.services.providers.recommendation_service import RecommendationService


class ComparisonEngine:
    """RAG-first provider comparison using structured rates + parsed query context."""

    def __init__(self, db):
        self.db = db
        self.recommendations = RecommendationService(db)

    async def compare(self, parsed: ParsedQuery) -> dict:
        if parsed.intent != "provider_comparison" and not parsed.providers:
            if parsed.weight_kg and (parsed.origin or parsed.destination):
                parsed.intent = "provider_comparison"

        if parsed.intent != "provider_comparison":
            return {"recommendations": [], "warnings": [], "assumptions": [], "labels": {}}

        assumptions = []
        if not parsed.origin:
            assumptions.append("Origin city not specified")
        if not parsed.destination:
            assumptions.append("Destination city not specified")
        if not parsed.weight_kg:
            assumptions.append("Weight not specified")

        if not parsed.origin or not parsed.destination or not parsed.weight_kg:
            return {
                "recommendations": [],
                "warnings": ["Need origin, destination, and weight for a meaningful comparison"],
                "assumptions": assumptions,
                "labels": {},
                "missing_fields": parsed.missing_fields,
            }

        origin = _country_from_city(parsed.origin, parsed.domestic)
        destination = _country_from_city(parsed.destination, parsed.domestic)

        result = await self.recommendations.recommend(
            origin_country=origin,
            destination_country=destination,
            weight=parsed.weight_kg,
            priority=parsed.priority,
            cod_required=parsed.cod or False,
        )

        labels = {
            "cheapest": "BEST FOR CHEAPEST",
            "fastest": "BEST FOR SPEED",
            "balanced": "BEST FOR BALANCED",
        }
        if parsed.cod:
            labels["cod"] = "BEST FOR COD"

        recs = result.get("recommendations", [])
        for i, rec in enumerate(recs[:3]):
            price = rec.get("price") or {}
            if price.get("status") == "quote_unavailable":
                rec["price_label"] = "UNAVAILABLE"
            elif price.get("source") == "official_rate":
                rec["price_label"] = "STORED_VERIFIED_RATE"
            else:
                rec["price_label"] = "UNAVAILABLE"

        return {
            "recommendations": recs,
            "warnings": result.get("warnings", []),
            "assumptions": assumptions,
            "labels": labels,
            "comparison_context": parsed.to_dict(),
        }


def _country_from_city(city: str, domestic: bool | None) -> str:
    pakistan_cities = {
        "lahore", "karachi", "islamabad", "rawalpindi", "faisalabad", "multan",
        "peshawar", "quetta", "sialkot", "hyderabad", "gujranwala",
    }
    if city.lower() in pakistan_cities or domestic:
        return "Pakistan"
    mapping = {"dubai": "UAE", "uae": "UAE", "london": "UK", "usa": "USA"}
    return mapping.get(city.lower(), city)
