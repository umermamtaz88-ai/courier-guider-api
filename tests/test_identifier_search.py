from app.ai.rag.identifier_search import extract_identifiers


def test_extract_shipment_reference():
    ids = extract_identifiers("Please check SHP-ABC12345 status")
    assert "SHP-ABC12345" in ids


def test_extract_demo_order():
    ids = extract_identifiers("Order DEMO-ORD-001 not delivered")
    assert "DEMO-ORD-001" in ids
