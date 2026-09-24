"""
Tests for the purchases router  →  /api/purchases
"""
import pytest
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _purchase_payload(item_id, quantity=10, unit_cost=15.0, supplier_name="Supplier X"):
    return {
        "supplier_name": supplier_name,
        "supplier_invoice": "SI-001",
        "items": [{"item_id": item_id, "quantity": quantity, "unit_cost": unit_cost}],
    }


# ---------------------------------------------------------------------------
# POST /api/purchases
# ---------------------------------------------------------------------------

def test_create_purchase_success(client, sample_item):
    qty = 20
    unit_cost = 30.0
    payload = _purchase_payload(sample_item.id, quantity=qty, unit_cost=unit_cost)
    response = client.post("/api/purchases", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()

    assert data["purchase_number"].startswith("PUR-")
    assert data["status"] == "received"
    assert data["supplier_name"] == "Supplier X"
    assert data["total_amount"] == round(qty * unit_cost, 2)
    assert len(data["items"]) == 1
    assert data["items"][0]["line_total"] == round(qty * unit_cost, 2)


def test_create_purchase_no_items(client):
    payload = {"supplier_name": "Someone", "items": []}
    response = client.post("/api/purchases", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400


def test_create_purchase_item_not_found(client):
    payload = _purchase_payload(item_id=99999, quantity=5)
    response = client.post("/api/purchases", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_create_purchase_adds_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    purchase_qty = 30

    client.post(
        "/api/purchases",
        json=_purchase_payload(sample_item.id, quantity=purchase_qty),
        headers=AUTH_HEADERS,
    )

    db.refresh(sample_item)
    assert sample_item.quantity == original_qty + purchase_qty


def test_create_purchase_auto_numbers(client, sample_item):
    r1 = client.post("/api/purchases", json=_purchase_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)
    r2 = client.post("/api/purchases", json=_purchase_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)

    assert r1.status_code == 201
    assert r2.status_code == 201

    num1 = int(r1.json()["purchase_number"].split("-")[1])
    num2 = int(r2.json()["purchase_number"].split("-")[1])
    assert num2 == num1 + 1


def test_create_purchase_multi_item_total(client, db, sample_item, sample_item_b):
    payload = {
        "supplier_name": "Multi Supplier",
        "items": [
            {"item_id": sample_item.id, "quantity": 5, "unit_cost": 10.0},
            {"item_id": sample_item_b.id, "quantity": 3, "unit_cost": 20.0},
        ],
    }
    response = client.post("/api/purchases", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    expected_total = round(5 * 10.0 + 3 * 20.0, 2)
    assert data["total_amount"] == expected_total


# ---------------------------------------------------------------------------
# GET /api/purchases
# ---------------------------------------------------------------------------

def test_get_all_purchases_empty(client):
    response = client.get("/api/purchases", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_purchases(client, sample_item):
    client.post("/api/purchases", json=_purchase_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)
    client.post("/api/purchases", json=_purchase_payload(sample_item.id, quantity=1), headers=AUTH_HEADERS)

    response = client.get("/api/purchases", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # ordered newest first
    assert data[0]["id"] > data[1]["id"]


# ---------------------------------------------------------------------------
# GET /api/purchases/{id}
# ---------------------------------------------------------------------------

def test_get_purchase_by_id(client, sample_item):
    create_resp = client.post(
        "/api/purchases",
        json=_purchase_payload(sample_item.id, quantity=5),
        headers=AUTH_HEADERS,
    )
    purchase_id = create_resp.json()["id"]

    response = client.get(f"/api/purchases/{purchase_id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == purchase_id
    assert len(data["items"]) == 1


def test_get_purchase_not_found(client):
    response = client.get("/api/purchases/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/purchases/{id}/cancel
# ---------------------------------------------------------------------------

def test_cancel_purchase(client, db, sample_item):
    purchase_qty = 20
    stock_before = sample_item.quantity

    create_resp = client.post(
        "/api/purchases",
        json=_purchase_payload(sample_item.id, quantity=purchase_qty),
        headers=AUTH_HEADERS,
    )
    purchase_id = create_resp.json()["id"]

    # Verify stock increased after purchase
    db.refresh(sample_item)
    assert sample_item.quantity == stock_before + purchase_qty

    cancel_resp = client.patch(f"/api/purchases/{purchase_id}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    # Stock must be back to original
    db.refresh(sample_item)
    assert sample_item.quantity == stock_before


def test_cancel_purchase_stock_floor_at_zero(client, db, sample_item):
    """
    If the item stock was consumed between purchase and cancel,
    cancellation should floor at 0 rather than going negative.
    """
    purchase_qty = 50

    # Create the purchase (adds 50 to stock)
    create_resp = client.post(
        "/api/purchases",
        json=_purchase_payload(sample_item.id, quantity=purchase_qty),
        headers=AUTH_HEADERS,
    )
    purchase_id = create_resp.json()["id"]

    # Manually set item quantity to 0 to simulate all stock being sold
    db.refresh(sample_item)
    sample_item.quantity = 0
    db.commit()

    # Cancelling should not make quantity negative
    cancel_resp = client.patch(f"/api/purchases/{purchase_id}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200

    db.refresh(sample_item)
    assert sample_item.quantity >= 0


def test_cancel_purchase_already_cancelled(client, sample_item):
    create_resp = client.post(
        "/api/purchases",
        json=_purchase_payload(sample_item.id, quantity=5),
        headers=AUTH_HEADERS,
    )
    purchase_id = create_resp.json()["id"]

    client.patch(f"/api/purchases/{purchase_id}/cancel", headers=AUTH_HEADERS)
    second = client.patch(f"/api/purchases/{purchase_id}/cancel", headers=AUTH_HEADERS)
    assert second.status_code == 400
    assert "already cancelled" in second.json()["detail"].lower()


def test_cancel_purchase_not_found(client):
    response = client.patch("/api/purchases/999/cancel", headers=AUTH_HEADERS)
    assert response.status_code == 404
