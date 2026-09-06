"""Lightweight RAG evaluation cases — expected behaviors, not live LLM."""

EVAL_CASES = [
    {
        "id": "domestic_8kg",
        "query": "Which is better, TCS or Leopards for an 8kg clothing shipment from Lahore to Karachi?",
        "expected_intent": "compare_providers",
        "expected_entities": {"weight_kg": 8.0, "origin": "Lahore", "destination": "Karachi"},
        "forbidden_claims": ["always cheapest", "always fastest"],
    },
    {
        "id": "price_unverified",
        "query": "How much will it cost right now?",
        "expected_behavior": "must_not_invent_price",
        "forbidden_claims": ["It will cost PKR"],
    },
    {
        "id": "roman_urdu",
        "query": "Mera 8kg ka kapron ka parcel Lahore se Karachi bhejna hai",
        "expected_entities": {"weight_kg": 8.0},
    },
]


def test_eval_case_parsing():
    from app.ai.query_parser import parse_query
    from app.ai.intents import IntentDetector

    case = EVAL_CASES[0]
    intent = IntentDetector().detect(case["query"])
    parsed = parse_query(case["query"], intent=intent.value)
    assert parsed.weight_kg == 8.0
    assert parsed.origin == "Lahore"
    assert parsed.destination == "Karachi"


def test_roman_urdu_clothing_query():
    from app.ai.query_normalizer import normalize_query
    from app.ai.query_parser import parse_query

    norm = normalize_query(EVAL_CASES[2]["query"])
    parsed = parse_query(norm, intent="compare_providers")
    assert parsed.weight_kg == 8.0
    assert "clothing" in (parsed.product or "") or "cloth" in norm
