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


# ---------------------------------------------------------------------------
# Phase 4 — Extended inventory tests
# ---------------------------------------------------------------------------

def test_create_item_reject_negative_quantity(client):
    """Pydantic ge=0 constraint should reject negative quantity."""
    payload = {"name": "Neg Qty", "quantity": -5, "unit": "pcs"}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_cost_price(client):
    payload = {"name": "Neg CP", "cost_price": -10.0}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_selling_price(client):
    payload = {"name": "Neg SP", "selling_price": -1.0}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_wholesale_price(client):
    payload = {"name": "Neg WP", "wholesale_price": -1.0}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_dealer_price(client):
    payload = {"name": "Neg DP", "dealer_price": -1.0}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_gst_rate(client):
    payload = {"name": "Neg GST", "gst_rate": -5.0}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_reject_negative_low_stock_threshold(client):
    payload = {"name": "Neg LST", "low_stock_threshold": -1}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_update_item_reject_negative_quantity(client, sample_item):
    response = client.put(
        f"/api/items/{sample_item.id}",
        json={"quantity": -1},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_update_item_reject_negative_prices(client, sample_item):
    for field in ("cost_price", "selling_price", "wholesale_price", "dealer_price"):
        response = client.put(
            f"/api/items/{sample_item.id}",
            json={field: -1.0},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 422, f"{field} should reject negative"


def test_create_item_empty_name_rejected(client):
    response = client.post("/api/items", json={"name": ""}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_item_all_price_tiers(client):
    payload = {
        "name": "Multi Tier",
        "quantity": 10,
        "cost_price": 50.0,
        "wholesale_price": 70.0,
        "dealer_price": 80.0,
        "selling_price": 100.0,
        "unit": "pcs",
    }
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["wholesale_price"] == 70.0
    assert data["dealer_price"] == 80.0


def test_create_item_with_hsn_and_gst(client):
    payload = {
        "name": "HSN Item",
        "hsn_code": "3307",
        "gst_rate": 18.0,
        "unit": "pcs",
    }
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["hsn_code"] == "3307"
    assert data["gst_rate"] == 18.0


def test_update_item_db_state(client, db, sample_item):
    """Verify DB state after update, not just HTTP response."""
    client.put(
        f"/api/items/{sample_item.id}",
        json={"selling_price": 999.0, "category": "Updated"},
        headers=AUTH_HEADERS,
    )
    db.refresh(sample_item)
    assert sample_item.selling_price == 999.0
    assert sample_item.category == "Updated"


def test_delete_item_db_state(client, db, sample_item):
    """Confirm item is actually gone from DB."""
    item_id = sample_item.id
    client.delete(f"/api/items/{item_id}", headers=AUTH_HEADERS)
    result = db.query(models.Item).filter(models.Item.id == item_id).first()
    assert result is None


def test_stock_update_db_state(client, db, sample_item):
    """Verify DB state after stock adjustment."""
    orig = sample_item.quantity
    client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": 15},
        headers=AUTH_HEADERS,
    )
    db.refresh(sample_item)
    assert sample_item.quantity == orig + 15


def test_stats_low_stock_count_multiple(client, db):
    """Multiple items below threshold."""
    db.add(models.Item(name="L1", quantity=1, low_stock_threshold=10, unit="pcs"))
    db.add(models.Item(name="L2", quantity=5, low_stock_threshold=10, unit="pcs"))
    db.add(models.Item(name="H1", quantity=100, low_stock_threshold=10, unit="pcs"))
    db.commit()

    data = client.get("/api/stats", headers=AUTH_HEADERS).json()
    assert data["low_stock_count"] == 2
    assert data["total_items"] == 3


def test_stats_categories_no_duplicates(client, db):
    """Duplicate categories should appear once in the list."""
    db.add(models.Item(name="A1", category="Cat", quantity=1, unit="pcs"))
    db.add(models.Item(name="A2", category="Cat", quantity=1, unit="pcs"))
    db.commit()

    data = client.get("/api/stats", headers=AUTH_HEADERS).json()
    assert data["categories"] == ["Cat"]


def test_stats_total_value_tiny_cost(client, db):
    """Inventory value with very small cost_price."""
    db.add(models.Item(name="Tiny", quantity=1000, cost_price=0.001, unit="pcs"))
    db.commit()

    data = client.get("/api/stats", headers=AUTH_HEADERS).json()
    assert data["total_value"] == 1.0  # 1000 * 0.001 = 1.0


def test_create_item_zero_quantity_default(client):
    """Default quantity is 0 if not provided."""
    response = client.post("/api/items", json={"name": "ZeroQty"}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["quantity"] == 0


def test_update_item_preserves_other_fields(client, sample_item):
    """Updating one field should not affect others."""
    original_qty = sample_item.quantity
    response = client.put(
        f"/api/items/{sample_item.id}",
        json={"category": "NewCat"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == original_qty
