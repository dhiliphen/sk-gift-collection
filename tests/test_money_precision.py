"""
Tests for Decimal-based money handling and the centralized GST tax engine
(app/services/tax.py). These specifically target the float-precision bugs
that Decimal fixes, and confirm the JSON wire format (plain numbers, not
strings) is unchanged for existing API consumers.
"""
from decimal import Decimal
import json
import pytest
from tests.conftest import AUTH_HEADERS
from app import models
from app.money import Money
from app.services.tax import calculate_line_tax, split_cgst_sgst
from pydantic import BaseModel


class _MoneyHolder(BaseModel):
    value: Money


# ---------------------------------------------------------------------------
# SQLite round-trip corruption: a Numeric(12,2) column stores through a
# float regardless of declared scale, and SQLAlchemy's sqlite dialect
# re-rounds via Python's float round() on read — reintroducing the exact
# binary-float bug this migration exists to fix, unless input is already
# quantized to 2dp before it ever reaches the column.
# ---------------------------------------------------------------------------

def test_money_type_quantizes_excess_precision_on_input():
    """Without quantizing at the boundary, 2.675 would round-trip through
    SQLite's float storage and come back as 2.67 (see the float-rounding
    regression test above). Quantizing here means it's already exactly
    2.68 by the time it reaches the database, so the lossy round-trip is
    a no-op."""
    assert _MoneyHolder(value=2.675).value == Decimal("2.68")


def test_item_price_survives_sqlite_round_trip_with_excess_precision(client, db):
    """End-to-end regression for the bug this test module's sibling test
    documents: creating an item with a 3-decimal price must come back
    correctly rounded (2.68), not silently truncated by the SQLite
    round-trip (which would otherwise give 2.67)."""
    response = client.post(
        "/api/items",
        json={"name": "Fractional Price Item", "selling_price": 2.675, "quantity": 1, "unit": "pcs"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201
    assert response.json()["selling_price"] == 2.68

    # Re-fetch to force a fresh read from the database, not just the
    # in-memory object from the create() call.
    item_id = response.json()["id"]
    refetched = client.get(f"/api/items/{item_id}", headers=AUTH_HEADERS)
    assert refetched.json()["selling_price"] == 2.68


# ---------------------------------------------------------------------------
# Regression: classic float rounding trap
# ---------------------------------------------------------------------------

def test_float_would_round_2675_down_but_decimal_rounds_correctly():
    """Sanity check documenting *why* this migration matters: plain float
    arithmetic rounds 2.675 down to 2.67 (binary representation is actually
    2.67499999999999982...), while exact Decimal rounds it correctly to 2.68."""
    assert round(2.675, 2) == 2.67          # the float bug
    assert round(Decimal("2.675"), 2) == Decimal("2.68")  # the fix


def test_bill_line_taxable_uses_exact_decimal_rounding(client, db):
    """A unit price of 2.675 with qty=1 must round to 2.68 (correct), not
    2.67 (the float bug this migration fixes)."""
    item = models.Item(name="Precision Item", quantity=10, selling_price=2.675, gst_rate=0, unit="pcs")
    db.add(item); db.commit(); db.refresh(item)

    payload = {
        "customer_name": "Precision Test", "customer_type": "retailer",
        "items": [{"item_id": item.id, "quantity": 1, "unit_price": 2.675}],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    data = response.json()

    assert response.status_code == 201
    assert data["items"][0]["taxable_amount"] == 2.68
    assert data["total_amount"] == 2.68


def test_many_small_lines_sum_exactly(client, db):
    """10 lines of 0.10 each must sum to exactly 1.00 — repeated float
    addition of 0.1 famously drifts (0.1*10 != 1.0 in binary float in some
    accumulation orders); Decimal addition is exact."""
    item = models.Item(name="Dime Item", quantity=100, selling_price=0.10, gst_rate=0, unit="pcs")
    db.add(item); db.commit(); db.refresh(item)

    payload = {
        "customer_name": "Sum Test", "customer_type": "retailer",
        "items": [{"item_id": item.id, "quantity": 1, "unit_price": 0.10} for _ in range(10)],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    data = response.json()

    assert response.status_code == 201
    assert data["taxable_amount"] == 1.00
    assert data["total_amount"] == 1.00


# ---------------------------------------------------------------------------
# JSON wire-format contract: money fields are still plain numbers
# ---------------------------------------------------------------------------

def test_money_fields_serialize_as_json_numbers_not_strings(client, sample_item):
    """Existing frontend does bill.total_amount.toFixed(2) etc. — the API
    must keep returning plain numbers, never a string, for money fields."""
    payload = {
        "customer_name": "Wire Format Test", "customer_type": "retailer",
        "items": [{"item_id": sample_item.id, "quantity": 2, "unit_price": 49.99}],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    raw_text = response.text
    parsed = json.loads(raw_text)

    for field in ("taxable_amount", "igst_amount", "total_amount", "amount_paid", "balance_due"):
        assert isinstance(parsed[field], (int, float)), f"{field} should be a JSON number, got {type(parsed[field])}"
    for field in ("unit_price", "gst_rate", "taxable_amount", "igst_amount", "line_total"):
        assert isinstance(parsed["items"][0][field], (int, float))


def test_item_money_fields_serialize_as_numbers(client):
    response = client.post(
        "/api/items",
        json={"name": "Wire Format Item", "selling_price": 199.99, "gst_rate": 18, "quantity": 5},
        headers=AUTH_HEADERS,
    )
    data = json.loads(response.text)
    for field in ("cost_price", "wholesale_price", "dealer_price", "selling_price", "gst_rate"):
        assert isinstance(data[field], (int, float))


# ---------------------------------------------------------------------------
# Centralized tax engine (app/services/tax.py) — unit tests
# ---------------------------------------------------------------------------

def test_calculate_line_tax_basic():
    result = calculate_line_tax(3, Decimal("100.00"), Decimal("18"))
    assert result == {
        "taxable_amount": Decimal("300.00"),
        "tax_amount": Decimal("54.00"),
        "line_total": Decimal("354.00"),
    }


def test_calculate_line_tax_zero_rate():
    result = calculate_line_tax(5, Decimal("20.00"), Decimal("0"))
    assert result["tax_amount"] == Decimal("0.00")
    assert result["line_total"] == Decimal("100.00")


def test_calculate_line_tax_precision_case():
    """The 2.675 case again, exercised directly against the tax engine."""
    result = calculate_line_tax(1, Decimal("2.675"), Decimal("0"))
    assert result["taxable_amount"] == Decimal("2.68")


def test_split_cgst_sgst_even_split():
    result = split_cgst_sgst(Decimal("300.00"), Decimal("18"))
    assert result["cgst"] == Decimal("27.00")
    assert result["sgst"] == Decimal("27.00")
    assert result["total_tax"] == Decimal("54.00")


def test_split_cgst_sgst_odd_cent_matches_half_then_double_order():
    """Documents the existing (pre-refactor) print-invoice arithmetic order:
    half is rounded first, then doubled — so an odd total tax cent can show
    a total_tax that differs by a cent from a straight taxable*rate/100."""
    # taxable=100.03, rate=18 -> raw tax = 18.0054 -> half = 9.0027 -> round 9.00 -> doubled 18.00
    result = split_cgst_sgst(Decimal("100.03"), Decimal("18"))
    assert result["cgst"] == result["sgst"]
    assert result["total_tax"] == result["cgst"] + result["sgst"]


# ---------------------------------------------------------------------------
# Print invoice still renders with Decimal-backed fields
# ---------------------------------------------------------------------------

def test_print_invoice_renders_with_decimal_fields(client, sample_item):
    bill_id = client.post(
        "/api/bills",
        json={
            "customer_name": "Print Test", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 3, "unit_price": 33.33}],
        },
        headers=AUTH_HEADERS,
    ).json()["id"]

    response = client.get(f"/api/bills/{bill_id}/print", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
