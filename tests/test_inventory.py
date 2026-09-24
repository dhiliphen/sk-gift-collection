"""
Tests for the inventory router  →  /api/items  and  /api/stats
"""
import pytest
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# GET /api/items
# ---------------------------------------------------------------------------

def test_get_all_items_empty(client):
    response = client.get("/api/items", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_items_returns_list(client, sample_item):
    response = client.get("/api/items", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Item"


# ---------------------------------------------------------------------------
# POST /api/items
# ---------------------------------------------------------------------------

def test_create_item(client):
    payload = {
        "name": "New Widget",
        "quantity": 25,
        "selling_price": 199.99,
        "cost_price": 80.0,
        "gst_rate": 12.0,
        "unit": "pcs",
    }
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Widget"
    assert data["quantity"] == 25
    assert data["selling_price"] == 199.99
    assert "id" in data


def test_create_item_duplicate_name(client):
    payload = {"name": "Dupe Item", "quantity": 10, "unit": "pcs"}
    client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_item_minimal_fields(client):
    """Only required field (name) — all others use defaults."""
    response = client.post("/api/items", json={"name": "Minimal"}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 0
    assert data["gst_rate"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/items/{id}
# ---------------------------------------------------------------------------

def test_get_item_by_id(client, sample_item):
    response = client.get(f"/api/items/{sample_item.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Test Item"


def test_get_item_not_found(client):
    response = client.get("/api/items/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/items/{id}
# ---------------------------------------------------------------------------

def test_update_item(client, sample_item):
    response = client.put(
        f"/api/items/{sample_item.id}",
        json={"selling_price": 149.99},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["selling_price"] == 149.99


def test_update_item_multiple_fields(client, sample_item):
    response = client.put(
        f"/api/items/{sample_item.id}",
        json={"selling_price": 75.0, "category": "Electronics", "gst_rate": 5.0},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["selling_price"] == 75.0
    assert data["category"] == "Electronics"
    assert data["gst_rate"] == 5.0


def test_update_item_not_found(client):
    response = client.put(
        "/api/items/999",
        json={"selling_price": 99.0},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/items/{id}/stock
# ---------------------------------------------------------------------------

def test_update_stock_add(client, sample_item):
    original_qty = sample_item.quantity
    response = client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": 10},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == original_qty + 10


def test_update_stock_deduct(client, sample_item):
    original_qty = sample_item.quantity
    response = client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": -5},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == original_qty - 5


def test_update_stock_deduct_to_zero(client, sample_item):
    """Deducting exactly the available quantity should succeed."""
    response = client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": -sample_item.quantity},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 0


def test_update_stock_below_zero(client, sample_item):
    response = client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": -(sample_item.quantity + 1)},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 400
    assert "below zero" in response.json()["detail"].lower()


def test_update_stock_item_not_found(client):
    response = client.patch(
        "/api/items/999/stock",
        json={"quantity_change": 5},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/items/{id}
# ---------------------------------------------------------------------------

def test_delete_item(client, sample_item):
    response = client.delete(f"/api/items/{sample_item.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204
    # Confirm it is gone
    get_response = client.get(f"/api/items/{sample_item.id}", headers=AUTH_HEADERS)
    assert get_response.status_code == 404


def test_delete_item_not_found(client):
    response = client.delete("/api/items/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_filter_by_category(client, db):
    db.add(models.Item(name="Cat A Item", category="Furniture", quantity=5, unit="pcs"))
    db.add(models.Item(name="Cat B Item", category="Electronics", quantity=3, unit="pcs"))
    db.commit()

    response = client.get("/api/items?category=Furniture", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["category"] == "Furniture"


def test_filter_low_stock(client, db):
    # quantity (5) <= low_stock_threshold (10) → low stock
    db.add(models.Item(name="Low Stock Item", quantity=5, low_stock_threshold=10, unit="pcs"))
    # quantity (50) > low_stock_threshold (10) → not low stock
    db.add(models.Item(name="Plenty Item", quantity=50, low_stock_threshold=10, unit="pcs"))
    db.commit()

    response = client.get("/api/items?low_stock=true", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Low Stock Item"


def test_filter_low_stock_boundary(client, db):
    """Item with quantity exactly equal to threshold is considered low stock."""
    db.add(models.Item(name="Boundary Item", quantity=10, low_stock_threshold=10, unit="pcs"))
    db.commit()

    response = client.get("/api/items?low_stock=true", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------

def test_stats_empty(client):
    response = client.get("/api/stats", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["total_value"] == 0.0
    assert data["low_stock_count"] == 0
    assert data["categories"] == []


def test_stats(client, db):
    db.add(models.Item(
        name="Item 1", quantity=10, cost_price=50.0,
        low_stock_threshold=5, category="Cat1", unit="pcs",
    ))
    db.add(models.Item(
        name="Item 2", quantity=3, cost_price=20.0,
        low_stock_threshold=10, category="Cat2", unit="pcs",
    ))
    db.commit()

    response = client.get("/api/stats", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["total_items"] == 2
    # total_value = 10*50 + 3*20 = 560
    assert data["total_value"] == 560.0
    # Item 2 has qty(3) <= threshold(10) → low stock
    assert data["low_stock_count"] == 1
    assert set(data["categories"]) == {"Cat1", "Cat2"}


def test_stats_total_value_calculation(client, db):
    """total_value uses cost_price × quantity, not selling_price."""
    db.add(models.Item(
        name="Priced Item", quantity=4,
        cost_price=25.0, selling_price=100.0, unit="pcs",
    ))
    db.commit()

    data = client.get("/api/stats", headers=AUTH_HEADERS).json()
    assert data["total_value"] == 100.0   # 4 × 25, not 4 × 100
