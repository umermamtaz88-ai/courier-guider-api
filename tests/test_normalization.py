from app.ai.query_normalizer import normalize_query
from app.services.address.address_service import normalize_address


def test_roman_urdu_normalization():
    result = normalize_query("parcel kahan hai track karo")
    assert "shipment" in result
    assert "tracking" in result


def test_address_normalization_lahore():
    result = normalize_address("House 12, DHA Phase 5, Lahore")
    assert result["city"] == "Lahore"
    assert result["country"] == "Pakistan"
    assert result["validation_status"] == "normalized"
