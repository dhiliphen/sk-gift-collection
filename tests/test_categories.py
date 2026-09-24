"""
Tests for the categories router  →  /api/categories
"""
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# GET /api/categories
# ---------------------------------------------------------------------------

def test_get_all_categories_empty(client):
    response = client.get("/api/categories", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_categories(client, db):
    db.add(models.Category(name="Clothing"))
    db.add(models.Category(name="Electronics"))
    db.commit()

    response = client.get("/api/categories", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# POST /api/categories
# ---------------------------------------------------------------------------

def test_create_category(client):
    response = client.post("/api/categories", json={"name": "Toys"}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Toys"
    assert "id" in data


def test_create_category_duplicate(client):
    client.post("/api/categories", json={"name": "Dupe Cat"}, headers=AUTH_HEADERS)
    response = client.post("/api/categories", json={"name": "Dupe Cat"}, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_category_empty_name(client):
    """Empty name should be rejected by Pydantic validation."""
    response = client.post("/api/categories", json={"name": ""}, headers=AUTH_HEADERS)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/categories/{id}
# ---------------------------------------------------------------------------

def test_get_category_by_id(client, db):
    cat = models.Category(name="Stationery")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    response = client.get(f"/api/categories/{cat.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Stationery"


def test_get_category_not_found(client):
    response = client.get("/api/categories/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/categories/{id}
# ---------------------------------------------------------------------------

def test_update_category(client, db):
    cat = models.Category(name="Old Name")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    response = client.put(
        f"/api/categories/{cat.id}",
        json={"name": "New Name"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_update_category_not_found(client):
    response = client.put(
        "/api/categories/999",
        json={"name": "Whatever"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/categories/{id}
# ---------------------------------------------------------------------------

def test_delete_category(client, db):
    cat = models.Category(name="To Delete")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    response = client.delete(f"/api/categories/{cat.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204

    get_resp = client.get(f"/api/categories/{cat.id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404


def test_delete_category_not_found(client):
    response = client.delete("/api/categories/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_categories_ordered_by_name(client, db):
    for name in ["Zebra", "Apple", "Mango", "Berry"]:
        db.add(models.Category(name=name))
    db.commit()

    response = client.get("/api/categories", headers=AUTH_HEADERS)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == sorted(names)
    assert names[0] == "Apple"


# ---------------------------------------------------------------------------
# Phase 9 — Extended category tests
# ---------------------------------------------------------------------------

def test_create_category_max_length(client):
    """Category name max_length=50; exceeding should fail."""
    long_name = "A" * 51
    response = client.post("/api/categories", json={"name": long_name}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_category_exact_max_length(client):
    """Category name exactly at 50 chars should succeed."""
    name = "B" * 50
    response = client.post("/api/categories", json={"name": name}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == name


def test_update_category_max_length(client, db):
    cat = models.Category(name="OrigCat")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    long_name = "C" * 51
    response = client.put(
        f"/api/categories/{cat.id}",
        json={"name": long_name},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_update_category_db_state(client, db):
    cat = models.Category(name="DBState")
    db.add(cat)
    db.commit()
    db.refresh(cat)

    client.put(f"/api/categories/{cat.id}", json={"name": "Renamed"}, headers=AUTH_HEADERS)
    db.refresh(cat)
    assert cat.name == "Renamed"
