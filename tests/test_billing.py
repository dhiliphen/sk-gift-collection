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
