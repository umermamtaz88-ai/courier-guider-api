import pytest

from app.services.rules.quote_engine import (
    calculate_billable_weight,
    calculate_quote_breakdown,
    calculate_volumetric_weight,
    reconcile_cod,
)
from decimal import Decimal


def test_volumetric_weight():
    assert calculate_volumetric_weight(30, 20, 10, 5000) == 1.2


def test_billable_weight():
    assert calculate_billable_weight(1.0, 1.5) == 1.5


def test_quote_breakdown():
    result = calculate_quote_breakdown(base_charge=Decimal("100"), weight_charge=Decimal("50"))
    assert result["total"] == 150.0


def test_cod_reconcile_matched():
    result = reconcile_cod(
        order_expected=Decimal("1000"),
        shipment_cod=Decimal("1000"),
        provider_collected=Decimal("1000"),
        provider_settled=Decimal("1000"),
        company_received=Decimal("1000"),
    )
    assert result["status"] == "matched"


def test_cod_reconcile_discrepancy():
    result = reconcile_cod(
        order_expected=Decimal("1000"),
        shipment_cod=Decimal("900"),
        provider_collected=None,
        provider_settled=None,
        company_received=None,
    )
    assert result["status"] == "SETTLEMENT_DISCREPANCY"
    assert len(result["discrepancies"]) == 1
