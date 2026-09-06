from app.ai.query_parser import parse_query


def test_provider_comparison_parsing():
    parsed = parse_query(
        "I have 8kg clothes from Lahore to Karachi. Which courier is better?",
        intent="compare_providers",
    )
    assert parsed.weight_kg == 8.0
    assert parsed.product == "clothing"
    assert parsed.origin == "Lahore"
    assert parsed.destination == "Karachi"
    assert parsed.intent == "provider_comparison"
    assert parsed.domestic is True


def test_international_parsing():
    parsed = parse_query("8kg clothes from Lahore to Dubai", intent="plan_shipment")
    assert parsed.international is True
    assert parsed.destination == "Dubai"


def test_cod_and_priority():
    parsed = parse_query("cheapest COD option for 5kg parcel", intent="compare_providers")
    assert parsed.cod is True
    assert parsed.priority == "cheapest"
    assert parsed.weight_kg == 5.0
