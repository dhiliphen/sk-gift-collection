"""
Tests for the suppliers router  →  /api/suppliers
"""
from tests.conftest import AUTH_HEADERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _supplier_payload(**kwargs):
    base = {"name": "ACME Corp"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# GET /api/suppliers
# ---------------------------------------------------------------------------

def test_get_all_suppliers_empty(client):
    response = client.get("/api/suppliers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_suppliers(client, sample_supplier):
    response = client.get("/api/suppliers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1


# ---------------------------------------------------------------------------
# POST /api/suppliers
# ---------------------------------------------------------------------------

def test_create_supplier(client):
    payload = {
        "name": "New Supplier",
        "contact_person": "John Doe",
        "phone": "9876543210",
        "email": "john@example.com",
        "address": "123 Main St",
    }
    response = client.post("/api/suppliers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Supplier"
    assert data["contact_person"] == "John Doe"
    assert "id" in data


def test_create_supplier_minimal(client):
    """Only the name is required."""
    response = client.post("/api/suppliers", json={"name": "Minimal Supplier"}, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == "Minimal Supplier"


def test_create_supplier_duplicate_name(client):
    client.post("/api/suppliers", json={"name": "Dupe Supplier"}, headers=AUTH_HEADERS)
    response = client.post("/api/suppliers", json={"name": "Dupe Supplier"}, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/suppliers/{id}
# ---------------------------------------------------------------------------

def test_get_supplier_by_id(client, sample_supplier):
    response = client.get(f"/api/suppliers/{sample_supplier.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Test Supplier"


def test_get_supplier_not_found(client):
    response = client.get("/api/suppliers/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/suppliers/{id}
# ---------------------------------------------------------------------------

def test_update_supplier(client, sample_supplier):
    response = client.put(
        f"/api/suppliers/{sample_supplier.id}",
        json={"phone": "1112223333"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "1112223333"


def test_update_supplier_name(client, sample_supplier):
    response = client.put(
        f"/api/suppliers/{sample_supplier.id}",
        json={"name": "Renamed Supplier"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Supplier"


def test_update_supplier_not_found(client):
    response = client.put(
        "/api/suppliers/999",
        json={"phone": "0000000000"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/suppliers/{id}
# ---------------------------------------------------------------------------

def test_delete_supplier(client, sample_supplier):
    response = client.delete(f"/api/suppliers/{sample_supplier.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204

    get_resp = client.get(f"/api/suppliers/{sample_supplier.id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404


def test_delete_supplier_not_found(client):
    response = client.delete("/api/suppliers/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Phase 8 — Extended supplier tests
# ---------------------------------------------------------------------------

def test_create_supplier_empty_name_rejected(client):
    response = client.post("/api/suppliers", json={"name": ""}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_update_supplier_db_state(client, db, sample_supplier):
    """Verify DB state after supplier update."""
    client.put(
        f"/api/suppliers/{sample_supplier.id}",
        json={"contact_person": "Jane"},
        headers=AUTH_HEADERS,
    )
    db.refresh(sample_supplier)
    assert sample_supplier.contact_person == "Jane"


def test_delete_supplier_db_state(client, db, sample_supplier):
    sid = sample_supplier.id
    client.delete(f"/api/suppliers/{sid}", headers=AUTH_HEADERS)
    from app.models import Supplier
    assert db.query(Supplier).filter(Supplier.id == sid).first() is None


def test_create_supplier_all_fields(client):
    payload = {
        "name": "Full Supplier",
        "contact_person": "Bob",
        "phone": "1234567890",
        "email": "bob@supply.com",
        "address": "456 Road",
    }
    response = client.post("/api/suppliers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["contact_person"] == "Bob"
    assert data["email"] == "bob@supply.com"
