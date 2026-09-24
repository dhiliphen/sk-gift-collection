"""
Tests for the customers router  →  /api/customers
"""
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# GET /api/customers
# ---------------------------------------------------------------------------

def test_get_all_customers_empty(client):
    response = client.get("/api/customers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_customers(client, sample_customer):
    response = client.get("/api/customers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1


# ---------------------------------------------------------------------------
# POST /api/customers
# ---------------------------------------------------------------------------

def test_create_customer(client):
    payload = {
        "name": "Jane Smith",
        "customer_type": "wholesaler",
        "phone": "9876543210",
        "email": "jane@example.com",
        "address": "456 Market Rd",
    }
    response = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Smith"
    assert data["customer_type"] == "wholesaler"
    assert "id" in data


def test_create_customer_minimal(client):
    response = client.post(
        "/api/customers",
        json={"name": "Min Customer", "customer_type": "retailer"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 201


def test_create_customer_invalid_type(client):
    """customer_type must match the enum pattern."""
    response = client.post(
        "/api/customers",
        json={"name": "Bad Type", "customer_type": "vip"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/customers/{id}
# ---------------------------------------------------------------------------

def test_get_customer_by_id(client, sample_customer):
    response = client.get(f"/api/customers/{sample_customer.id}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["name"] == "Test Customer"


def test_get_customer_not_found(client):
    response = client.get("/api/customers/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/customers/{id}
# ---------------------------------------------------------------------------

def test_update_customer(client, sample_customer):
    response = client.put(
        f"/api/customers/{sample_customer.id}",
        json={"phone": "5551234567"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "5551234567"


def test_update_customer_type(client, sample_customer):
    response = client.put(
        f"/api/customers/{sample_customer.id}",
        json={"customer_type": "dealer"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["customer_type"] == "dealer"


def test_update_customer_not_found(client):
    response = client.put(
        "/api/customers/999",
        json={"phone": "0000000000"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/customers/{id}
# ---------------------------------------------------------------------------

def test_delete_customer(client, sample_customer):
    response = client.delete(f"/api/customers/{sample_customer.id}", headers=AUTH_HEADERS)
    assert response.status_code == 204

    get_resp = client.get(f"/api/customers/{sample_customer.id}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404


def test_delete_customer_not_found(client):
    response = client.delete("/api/customers/999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Filtering and ordering
# ---------------------------------------------------------------------------

def test_filter_by_customer_type(client, db):
    db.add(models.Customer(name="Wholesale Co", customer_type="wholesaler"))
    db.add(models.Customer(name="Retail Shop", customer_type="retailer"))
    db.add(models.Customer(name="Dealer Ltd", customer_type="dealer"))
    db.commit()

    response = client.get("/api/customers?customer_type=wholesaler", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["customer_type"] == "wholesaler"


def test_filter_by_customer_type_multiple_matches(client, db):
    db.add(models.Customer(name="Retail A", customer_type="retailer"))
    db.add(models.Customer(name="Retail B", customer_type="retailer"))
    db.add(models.Customer(name="Wholesale X", customer_type="wholesaler"))
    db.commit()

    response = client.get("/api/customers?customer_type=retailer", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(c["customer_type"] == "retailer" for c in data)


def test_customers_ordered_by_name(client, db):
    db.add(models.Customer(name="Zara", customer_type="retailer"))
    db.add(models.Customer(name="Anna", customer_type="retailer"))
    db.add(models.Customer(name="Mike", customer_type="retailer"))
    db.commit()

    response = client.get("/api/customers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == sorted(names)
    assert names[0] == "Anna"


# ---------------------------------------------------------------------------
# Phase 7 — Extended customer tests
# ---------------------------------------------------------------------------

def test_duplicate_name_different_phone_allowed(client):
    """Same name is allowed when phone numbers differ."""
    r1 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer", "phone": "9000000001",
    }, headers=AUTH_HEADERS)
    r2 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer", "phone": "9000000002",
    }, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


def test_duplicate_name_different_address_allowed(client):
    """Same name is allowed when addresses differ."""
    r1 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer", "address": "Shop 1, Dharavi",
    }, headers=AUTH_HEADERS)
    r2 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer", "address": "Shop 2, Andheri",
    }, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r2.status_code == 201


def test_duplicate_name_same_phone_and_address_blocked(client):
    """Same name + same phone + same address → 400."""
    payload = {
        "name": "Ramesh Traders", "customer_type": "retailer",
        "phone": "9000000001", "address": "Shop 1, Dharavi",
    }
    r1 = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    r2 = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r2.status_code == 400
    assert "already exists" in r2.json()["detail"]


def test_duplicate_name_no_contact_info_blocked(client):
    """Same name with no phone and no address → blocked (indistinguishable records)."""
    payload = {"name": "Ghost Customer", "customer_type": "retailer"}
    r1 = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    r2 = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert r1.status_code == 201
    assert r2.status_code == 400


def test_regression_amb002_update_into_duplicate_blocked(client):
    """
    Regression for AMB-002. Updating a customer so it becomes identical
    (name + phone + address) to another customer must be blocked.
    """
    r1 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer",
        "phone": "9000000001", "address": "Shop 1",
    }, headers=AUTH_HEADERS)
    r2 = client.post("/api/customers", json={
        "name": "Ramesh Traders", "customer_type": "retailer",
        "phone": "9000000002", "address": "Shop 2",
    }, headers=AUTH_HEADERS)
    # Try to update r2 so it becomes identical to r1
    update = client.put(f"/api/customers/{r2.json()['id']}", json={
        "phone": "9000000001", "address": "Shop 1",
    }, headers=AUTH_HEADERS)
    assert update.status_code == 400


def test_update_customer_same_data_allowed(client):
    """Updating a customer with its own data (no actual change) must not block."""
    r = client.post("/api/customers", json={
        "name": "Self Update", "customer_type": "retailer",
        "phone": "9000000001", "address": "Shop 1",
    }, headers=AUTH_HEADERS)
    cid = r.json()["id"]
    update = client.put(f"/api/customers/{cid}", json={
        "phone": "9000000001", "address": "Shop 1",
    }, headers=AUTH_HEADERS)
    assert update.status_code == 200


def test_create_customer_empty_name_rejected(client):
    payload = {"name": "", "customer_type": "retailer"}
    response = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_customer_all_types(client):
    """All three customer types should be accepted."""
    for ctype in ("wholesaler", "dealer", "retailer"):
        resp = client.post(
            "/api/customers",
            json={"name": f"Test {ctype}", "customer_type": ctype},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["customer_type"] == ctype


def test_update_customer_db_state(client, db, sample_customer):
    """Verify DB state after update."""
    client.put(
        f"/api/customers/{sample_customer.id}",
        json={"name": "Updated Name"},
        headers=AUTH_HEADERS,
    )
    db.refresh(sample_customer)
    assert sample_customer.name == "Updated Name"


def test_delete_customer_db_state(client, db, sample_customer):
    """Confirm customer is actually gone from DB."""
    cid = sample_customer.id
    client.delete(f"/api/customers/{cid}", headers=AUTH_HEADERS)
    assert db.query(models.Customer).filter(models.Customer.id == cid).first() is None


def test_create_customer_with_all_fields(client):
    payload = {
        "name": "Full Customer",
        "customer_type": "dealer",
        "phone": "9876543210",
        "email": "full@example.com",
        "address": "123 Street",
    }
    response = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["phone"] == "9876543210"
    assert data["email"] == "full@example.com"
    assert data["address"] == "123 Street"
