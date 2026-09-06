from decimal import Decimal
from typing import Any


def calculate_volumetric_weight(length_cm: float, width_cm: float, height_cm: float, divisor: int) -> float:
    """Volumetric weight = (L x W x H) / divisor. Divisor comes from provider config."""
    if divisor <= 0:
        raise ValueError("divisor must be positive")
    return round((length_cm * width_cm * height_cm) / divisor, 3)


def calculate_billable_weight(actual_kg: float, volumetric_kg: float) -> float:
    return max(actual_kg, volumetric_kg)


def calculate_quote_breakdown(
    *,
    base_charge: Decimal,
    weight_charge: Decimal = Decimal("0"),
    fuel_surcharge: Decimal = Decimal("0"),
    cod_fee: Decimal = Decimal("0"),
    remote_area_fee: Decimal = Decimal("0"),
    tax: Decimal = Decimal("0"),
    other_fees: Decimal = Decimal("0"),
) -> dict[str, Any]:
    total = base_charge + weight_charge + fuel_surcharge + cod_fee + remote_area_fee + tax + other_fees
    return {
        "base_charge": float(base_charge),
        "weight_charge": float(weight_charge),
        "fuel_surcharge": float(fuel_surcharge),
        "cod_fee": float(cod_fee),
        "remote_area_fee": float(remote_area_fee),
        "tax": float(tax),
        "other_fees": float(other_fees),
        "total": float(total),
    }


def reconcile_cod(
    *,
    order_expected: Decimal | None,
    shipment_cod: Decimal | None,
    provider_collected: Decimal | None,
    provider_settled: Decimal | None,
    company_received: Decimal | None,
) -> dict[str, Any]:
    """Deterministic COD reconciliation — never use LLM for this."""
    discrepancies: list[dict] = []
    if order_expected is not None and shipment_cod is not None and order_expected != shipment_cod:
        discrepancies.append({
            "type": "order_shipment_mismatch",
            "expected": float(order_expected),
            "actual": float(shipment_cod),
        })
    if provider_collected is not None and provider_settled is not None:
        diff = provider_collected - provider_settled
        if diff != 0:
            discrepancies.append({
                "type": "settlement_discrepancy",
                "collected": float(provider_collected),
                "settled": float(provider_settled),
                "difference": float(diff),
            })
    if company_received is not None and provider_settled is not None:
        diff = provider_settled - company_received
        if diff != 0:
            discrepancies.append({
                "type": "company_receipt_discrepancy",
                "settled": float(provider_settled),
                "received": float(company_received),
                "difference": float(diff),
            })
    total_discrepancy = sum(d.get("difference", 0) for d in discrepancies if "difference" in d)
    return {
        "discrepancies": discrepancies,
        "total_discrepancy": total_discrepancy,
        "status": "matched" if not discrepancies else "SETTLEMENT_DISCREPANCY",
    }
