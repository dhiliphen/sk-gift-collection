"""
Tests for the units router  →  /api/units
"""
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# GET /api/units
# ---------------------------------------------------------------------------

def test_get_all_units_empty(client):
    response = client.get("/api/units", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_units(client, db):
    db.add(models.Unit(name="kg"))
    db.add(models.Unit(name="pcs"))
    db.commit()

    response = client.get("/api/units", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# POST /api/units
# ---------------------------------------------------------------------------

def test_create_unit(client):
    response = client.post("/api/units", json={"name": "litre"}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "litre"
    assert "id" in data


def test_create_unit_duplicate(client):
    client.post("/api/units", json={"name": "box"}, headers=AUTH_HEADERS)
    response = client.post("/api/units", json={"name": "box"}, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_create_unit_empty_name(client):
    """Empty name must be rejected by Pydantic validation."""
    response = client.post("/api/units", json={"name": ""}, headers=AUTH_HEADERS)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/units/{id}
# ---------------------------------------------------------------------------

def test_get_unit_by_id(client, db):
    unit = models.Unit(name="metre")
    db.add(unit)
    db.commit()
    db.refresh(unit)

    response = client.get(f"/api/units/{unit.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "metre"


def test_get_unit_not_found(client):
    response = client.get("/api/units/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/units/{id}
# ---------------------------------------------------------------------------

def test_update_unit(client, db):
    unit = models.Unit(name="old_unit")
    db.add(unit)
    db.commit()
    db.refresh(unit)

    response = client.put(
        f"/api/units/{unit.id}",
        json={"name": "new_unit"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "new_unit"


def test_update_unit_not_found(client):
    response = client.put(
        "/api/units/999",
        json={"name": "doesn't matter"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/units/{id}
# ---------------------------------------------------------------------------

def test_delete_unit(client, db):
    unit = models.Unit(name="to_delete")
    db.add(unit)
    db.commit()
    db.refresh(unit)

    response = client.delete(f"/api/units/{unit.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204

    get_resp = client.get(f"/api/units/{unit.id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404


def test_delete_unit_not_found(client):
    response = client.delete("/api/units/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_units_ordered_by_name(client, db):
    for name in ["pcs", "kg", "box", "dozen"]:
        db.add(models.Unit(name=name))
    db.commit()

    response = client.get("/api/units", headers=AUTH_HEADERS)
    assert response.status_code == 200
    names = [u["name"] for u in response.json()]
    assert names == sorted(names)
    assert names[0] == "box"


# ---------------------------------------------------------------------------
# Phase 9 — Extended unit tests
# ---------------------------------------------------------------------------

def test_create_unit_max_length(client):
    """Unit name max_length=20; exceeding should fail."""
    long_name = "U" * 21
    response = client.post("/api/units", json={"name": long_name}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_create_unit_exact_max_length(client):
    """Unit name exactly at 20 chars should succeed."""
    name = "V" * 20
    response = client.post("/api/units", json={"name": name}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == name


def test_update_unit_max_length(client, db):
    unit = models.Unit(name="orig")
    db.add(unit)
    db.commit()
    db.refresh(unit)

    long_name = "W" * 21
    response = client.put(
        f"/api/units/{unit.id}",
        json={"name": long_name},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


def test_update_unit_db_state(client, db):
    unit = models.Unit(name="dbcheck")
    db.add(unit)
    db.commit()
    db.refresh(unit)

    client.put(f"/api/units/{unit.id}", json={"name": "updated"}, headers=AUTH_HEADERS)
    db.refresh(unit)
    assert unit.name == "updated"
