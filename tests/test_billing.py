"""
Tests for the billing router  →  /api/bills
"""
import pytest
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bill_payload(item_id, quantity=2, unit_price=100.0, customer_name="Alice"):
    return {
        "customer_name": customer_name,
        "customer_type": "retailer",
        "items": [{"item_id": item_id, "quantity": quantity, "unit_price": unit_price}],
    }


# ---------------------------------------------------------------------------
# POST /api/bills
# ---------------------------------------------------------------------------

def test_create_bill_success(client, sample_item):
    qty = 3
    unit_price = 100.0
    payload = _bill_payload(sample_item.id, quantity=qty, unit_price=unit_price)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()

    assert data["invoice_number"].startswith("INV-")
    assert data["status"] == "paid"
    assert data["customer_name"] == "Alice"
    assert len(data["items"]) == 1

    bill_item = data["items"][0]
    expected_taxable = round(qty * unit_price, 2)
    expected_igst = round(expected_taxable * sample_item.gst_rate / 100, 2)
    expected_total = round(expected_taxable + expected_igst, 2)

    assert bill_item["taxable_amount"] == expected_taxable
    assert bill_item["igst_amount"] == expected_igst
    assert bill_item["line_total"] == expected_total
    assert data["taxable_amount"] == expected_taxable
    assert data["igst_amount"] == expected_igst
    assert data["total_amount"] == expected_total


def test_create_bill_deducts_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    qty_to_buy = 10

    client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=qty_to_buy),
        headers=AUTH_HEADERS,
    )

    db.refresh(sample_item)
    assert sample_item.quantity == original_qty - qty_to_buy


def test_create_bill_auto_numbers_sequentially(client, sample_item):
    r1 = client.post("/api/bills", json=_bill_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)
    r2 = client.post("/api/bills", json=_bill_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)

    assert r1.status_code == 201
    assert r2.status_code == 201

    inv1 = r1.json()["invoice_number"]
    inv2 = r2.json()["invoice_number"]

    assert inv1.startswith("INV-")
    assert inv2.startswith("INV-")

    # Both are zero-padded 4-digit numbers; second must be greater
    num1 = int(inv1.split("-")[1])
    num2 = int(inv2.split("-")[1])
    assert num2 == num1 + 1


def test_create_bill_no_items(client):
    payload = {"customer_name": "Bob", "customer_type": "retailer", "items": []}
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400


def test_create_bill_item_not_found(client):
    payload = _bill_payload(item_id=99999, quantity=1)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_create_bill_insufficient_stock(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=sample_item.quantity + 1)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()


def test_create_bill_atomic_on_failure(client, db):
    """
    If any line fails stock validation the entire bill is aborted
    and no stock is deducted from previously validated items.
    """
    item_a = models.Item(name="Atomic A", quantity=10, cost_price=10.0,
                         selling_price=20.0, gst_rate=0.0, unit="pcs")
    item_b = models.Item(name="Atomic B", quantity=2, cost_price=10.0,
                         selling_price=20.0, gst_rate=0.0, unit="pcs")
    db.add_all([item_a, item_b])
    db.commit()
    db.refresh(item_a)
    db.refresh(item_b)

    payload = {
        "customer_name": "Test",
        "customer_type": "retailer",
        "items": [
            {"item_id": item_a.id, "quantity": 5, "unit_price": 20.0},
            # item_b only has 2 in stock; requesting 5 should fail
            {"item_id": item_b.id, "quantity": 5, "unit_price": 20.0},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400

    # item_a stock must still be 10 (no deduction happened)
    db.refresh(item_a)
    assert item_a.quantity == 10


def test_create_bill_zero_gst(client, db):
    item = models.Item(name="Zero GST Item", quantity=50, cost_price=10.0,
                       selling_price=25.0, gst_rate=0.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=2, unit_price=25.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert data["igst_amount"] == 0.0
    assert data["items"][0]["igst_amount"] == 0.0


def test_bill_multiple_items(client, db, sample_item, sample_item_b):
    payload = {
        "customer_name": "Multi",
        "customer_type": "retailer",
        "items": [
            {"item_id": sample_item.id, "quantity": 2, "unit_price": 100.0},
            {"item_id": sample_item_b.id, "quantity": 3, "unit_price": 40.0},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201

    data = response.json()
    assert len(data["items"]) == 2

    computed_total = sum(i["line_total"] for i in data["items"])
    assert round(computed_total, 2) == round(data["total_amount"], 2)


# ---------------------------------------------------------------------------
# GET /api/bills
# ---------------------------------------------------------------------------

def test_get_all_bills_empty(client):
    response = client.get("/api/bills", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_bills(client, sample_item):
    client.post("/api/bills", json=_bill_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)
    client.post("/api/bills", json=_bill_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)

    response = client.get("/api/bills", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # ordered newest first (id desc)
    assert data[0]["id"] > data[1]["id"]


# ---------------------------------------------------------------------------
# GET /api/bills/{id}
# ---------------------------------------------------------------------------

def test_get_bill_by_id(client, sample_item):
    create_resp = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=2),
        headers=AUTH_HEADERS,
    )
    bill_id = create_resp.json()["id"]

    response = client.get(f"/api/bills/{bill_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == bill_id
    assert len(data["items"]) == 1


def test_get_bill_not_found(client):
    response = client.get("/api/bills/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/bills/{id}/cancel
# ---------------------------------------------------------------------------

def test_cancel_bill(client, db, sample_item):
    original_qty = sample_item.quantity
    qty_bought = 5

    create_resp = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=qty_bought),
        headers=AUTH_HEADERS,
    )
    bill_id = create_resp.json()["id"]

    cancel_resp = client.patch(f"/api/bills/{bill_id}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Stock must be restored to original
    db.refresh(sample_item)
    assert sample_item.quantity == original_qty


def test_cancel_bill_already_cancelled(client, sample_item):
    create_resp = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=1),
        headers=AUTH_HEADERS,
    )
    bill_id = create_resp.json()["id"]

    client.patch(f"/api/bills/{bill_id}/cancel", headers=AUTH_HEADERS)
    second_cancel = client.patch(f"/api/bills/{bill_id}/cancel", headers=AUTH_HEADERS)
    assert second_cancel.status_code == 400
    assert "already cancelled" in second_cancel.json()["detail"].lower()


def test_cancel_bill_not_found(client):
    response = client.patch("/api/bills/999/cancel", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_cancel_bill_stock_restores_correctly(client, db, sample_item, sample_item_b):
    """Cancelling a multi-item bill restores stock for all items."""
    qty_a = 4
    qty_b = 7
    orig_a = sample_item.quantity
    orig_b = sample_item_b.quantity

    payload = {
        "customer_name": "Cancel Test",
        "customer_type": "retailer",
        "items": [
            {"item_id": sample_item.id, "quantity": qty_a, "unit_price": 100.0},
            {"item_id": sample_item_b.id, "quantity": qty_b, "unit_price": 40.0},
        ],
    }
    bill_id = client.post("/api/bills", json=payload, headers=AUTH_HEADERS).json()["id"]
    client.patch(f"/api/bills/{bill_id}/cancel", headers=AUTH_HEADERS)

    db.refresh(sample_item)
    db.refresh(sample_item_b)
    assert sample_item.quantity == orig_a
    assert sample_item_b.quantity == orig_b


# ---------------------------------------------------------------------------
# Phase 6 — Extended billing tests
# ---------------------------------------------------------------------------

def test_gst_calculation_18_percent(client, db):
    """GST: taxable = qty * unit_price; igst = taxable * gst_rate/100; line_total = taxable + igst."""
    item = models.Item(name="GST18", quantity=100, cost_price=80.0,
                       selling_price=100.0, gst_rate=18.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=3, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()

    assert data["taxable_amount"] == 300.00
    assert data["igst_amount"] == 54.00
    assert data["total_amount"] == 354.00

    line = data["items"][0]
    assert line["taxable_amount"] == 300.00
    assert line["igst_amount"] == 54.00
    assert line["line_total"] == 354.00


def test_gst_calculation_fractional_price(client, db):
    """Fractional price: qty=7, price=13.33."""
    item = models.Item(name="Frac", quantity=100, cost_price=10.0,
                       selling_price=13.33, gst_rate=12.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=7, unit_price=13.33)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()

    expected_taxable = round(7 * 13.33, 2)  # 93.31
    expected_igst = round(expected_taxable * 12.0 / 100, 2)  # 11.20
    expected_total = round(expected_taxable + expected_igst, 2)  # 104.51

    assert data["taxable_amount"] == expected_taxable
    assert data["igst_amount"] == expected_igst
    assert data["total_amount"] == expected_total


def test_bill_rounding_per_line(client, db):
    """Each line total is rounded to 2dp; totals summed then rounded."""
    item_a = models.Item(name="RoundA", quantity=100, cost_price=10.0,
                         selling_price=33.33, gst_rate=18.0, unit="pcs")
    item_b = models.Item(name="RoundB", quantity=100, cost_price=10.0,
                         selling_price=66.67, gst_rate=5.0, unit="pcs")
    db.add_all([item_a, item_b])
    db.commit()
    db.refresh(item_a)
    db.refresh(item_b)

    payload = {
        "customer_name": "Round Test",
        "customer_type": "retailer",
        "items": [
            {"item_id": item_a.id, "quantity": 3, "unit_price": 33.33},
            {"item_id": item_b.id, "quantity": 2, "unit_price": 66.67},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()

    # Verify each line is rounded to 2dp
    for line in data["items"]:
        assert line["taxable_amount"] == round(line["taxable_amount"], 2)
        assert line["igst_amount"] == round(line["igst_amount"], 2)
        assert line["line_total"] == round(line["line_total"], 2)

    # Verify header totals
    assert data["total_amount"] == round(data["total_amount"], 2)


def test_bill_multiple_hsn_codes(client, db):
    """Multiple HSN codes in one bill -- verify items captured correctly."""
    item_a = models.Item(name="HSN_A", quantity=100, cost_price=10.0,
                         selling_price=50.0, gst_rate=18.0, hsn_code="3307",
                         unit="pcs")
    item_b = models.Item(name="HSN_B", quantity=100, cost_price=10.0,
                         selling_price=80.0, gst_rate=5.0, hsn_code="4901",
                         unit="pcs")
    db.add_all([item_a, item_b])
    db.commit()
    db.refresh(item_a)
    db.refresh(item_b)

    payload = {
        "customer_name": "HSN Test",
        "customer_type": "retailer",
        "items": [
            {"item_id": item_a.id, "quantity": 2, "unit_price": 50.0},
            {"item_id": item_b.id, "quantity": 3, "unit_price": 80.0},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()

    hsn_codes = {i["hsn_code"] for i in data["items"]}
    assert "3307" in hsn_codes
    assert "4901" in hsn_codes


def test_bill_atomicity_invalid_item_no_stock_deducted(client, db):
    """If one item_id is invalid, NO stock should be modified for any item."""
    item = models.Item(name="AtomValid", quantity=50, cost_price=10.0,
                       selling_price=20.0, gst_rate=0.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = {
        "customer_name": "Atom Test",
        "customer_type": "retailer",
        "items": [
            {"item_id": item.id, "quantity": 5, "unit_price": 20.0},
            {"item_id": 99999, "quantity": 1, "unit_price": 10.0},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 404

    db.refresh(item)
    assert item.quantity == 50


def test_bill_atomicity_insufficient_stock(client, db):
    """If any item has insufficient stock, NO stock should change."""
    item_a = models.Item(name="AtomOK", quantity=20, cost_price=10.0,
                         selling_price=20.0, gst_rate=0.0, unit="pcs")
    item_b = models.Item(name="AtomLow", quantity=3, cost_price=10.0,
                         selling_price=20.0, gst_rate=0.0, unit="pcs")
    db.add_all([item_a, item_b])
    db.commit()
    db.refresh(item_a)
    db.refresh(item_b)

    payload = {
        "customer_name": "Atom",
        "customer_type": "retailer",
        "items": [
            {"item_id": item_a.id, "quantity": 5, "unit_price": 20.0},
            {"item_id": item_b.id, "quantity": 10, "unit_price": 20.0},
        ],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400

    db.refresh(item_a)
    db.refresh(item_b)
    assert item_a.quantity == 20
    assert item_b.quantity == 3


def test_bill_customer_type_stored(client, sample_item):
    """Customer type is stored on the bill."""
    for ctype in ("retailer", "wholesaler", "dealer"):
        payload = {
            "customer_name": f"CT {ctype}",
            "customer_type": ctype,
            "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}],
        }
        response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
        assert response.status_code == 201
        assert response.json()["customer_type"] == ctype


def test_bill_invalid_customer_type(client, sample_item):
    """Invalid customer_type should be rejected."""
    payload = {
        "customer_name": "Bad",
        "customer_type": "vip",
        "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_zero_unit_price(client, db):
    """Zero unit_price should be allowed (ge=0 in schema)."""
    item = models.Item(name="FreeItem", quantity=10, cost_price=0.0,
                       selling_price=0.0, gst_rate=0.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=2, unit_price=0.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["total_amount"] == 0.0


def test_bill_negative_unit_price_rejected(client, sample_item):
    """Negative unit_price should be rejected (ge=0)."""
    payload = _bill_payload(sample_item.id, quantity=1, unit_price=-10.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_zero_quantity_rejected(client, sample_item):
    """Zero quantity should be rejected (gt=0)."""
    payload = _bill_payload(sample_item.id, quantity=0, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_negative_quantity_rejected(client, sample_item):
    """Negative quantity should be rejected."""
    payload = _bill_payload(sample_item.id, quantity=-1, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_missing_customer_name(client, sample_item):
    """Customer name is required."""
    payload = {
        "customer_type": "retailer",
        "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_empty_customer_name(client, sample_item):
    """Empty customer name should be rejected (min_length=1)."""
    payload = {
        "customer_name": "",
        "customer_type": "retailer",
        "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}],
    }
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_hsn_snapshot_from_item(client, db):
    """Bill items snapshot HSN code from the inventory item."""
    item = models.Item(name="HSNSnap", quantity=50, cost_price=10.0,
                       selling_price=100.0, gst_rate=18.0, hsn_code="1234",
                       unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=1, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["items"][0]["hsn_code"] == "1234"


def test_bill_unit_snapshot_from_item(client, db):
    """Bill items snapshot the unit from the inventory item."""
    item = models.Item(name="UnitSnap", quantity=50, cost_price=10.0,
                       selling_price=100.0, gst_rate=0.0, unit="kg")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=2, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["items"][0]["unit"] == "kg"


def test_bill_gst_rate_snapshot_from_item(client, db):
    """Bill items snapshot gst_rate from the item, not from bill payload."""
    item = models.Item(name="GSTSnap", quantity=50, cost_price=10.0,
                       selling_price=100.0, gst_rate=28.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=1, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["items"][0]["gst_rate"] == 28.0


def test_bill_print_endpoint(client, sample_item):
    """Print endpoint returns HTML 200 (requires correct template path)."""
    create_resp = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=1, unit_price=100.0),
        headers=AUTH_HEADERS,
    )
    bill_id = create_resp.json()["id"]

    print_resp = client.get(f"/api/bills/{bill_id}/print", headers=AUTH_HEADERS)
    assert print_resp.status_code == 200
    assert "text/html" in print_resp.headers.get("content-type", "")


def test_bill_print_not_found(client):
    """Print endpoint for non-existent bill returns 404."""
    response = client.get("/api/bills/99999/print", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_bill_db_state_after_create(client, db, sample_item):
    """Verify bill and bill items are in DB after creation."""
    payload = _bill_payload(sample_item.id, quantity=2, unit_price=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    bill_id = response.json()["id"]

    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    assert bill is not None
    assert bill.status == "paid"
    assert len(bill.items) == 1


def test_bill_cancel_db_state(client, db, sample_item):
    """Verify bill status in DB after cancellation."""
    payload = _bill_payload(sample_item.id, quantity=1, unit_price=100.0)
    resp = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    bill_id = resp.json()["id"]

    client.patch(f"/api/bills/{bill_id}/cancel", headers=AUTH_HEADERS)
    db.expire_all()
    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    assert bill.status == "cancelled"


def test_bill_exact_stock_purchase(client, db):
    """Buying exactly the full stock should succeed."""
    item = models.Item(name="ExactStock", quantity=5, cost_price=10.0,
                       selling_price=20.0, gst_rate=0.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=5, unit_price=20.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201

    db.refresh(item)
    assert item.quantity == 0


# ---------------------------------------------------------------------------
# Phase 13 — Money/Precision in billing
# ---------------------------------------------------------------------------

def test_bill_float_precision_sum(client, db):
    """Verify totals are rounded, not raw float sums (0.1 + 0.2 != 0.3 in float)."""
    item = models.Item(name="FloatPrec", quantity=100, cost_price=5.0,
                       selling_price=10.0, gst_rate=10.0, unit="pcs")
    db.add(item)
    db.commit()
    db.refresh(item)

    payload = _bill_payload(item.id, quantity=3, unit_price=10.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    data = response.json()

    # taxable=30.0, igst=3.0, total=33.0 -- clean numbers
    assert data["taxable_amount"] == 30.0
    assert data["igst_amount"] == 3.0
    assert data["total_amount"] == 33.0
