"""
Tests for security — Phase 12

Local-only security tests covering:
- SQL injection prevention (ORM should protect)
- XSS storage (no sanitisation in API layer)
- Auth bypass attempts
"""
import pytest
from tests.conftest import AUTH_HEADERS
from app import models


# ---------------------------------------------------------------------------
# SQL injection — ORM should prevent injection
# ---------------------------------------------------------------------------

def test_sql_injection_in_item_name(client):
    """
    Create an item with an SQL injection payload as the name.
    SQLAlchemy ORM parameterises queries, so this should safely create the item
    (or return 400/422 if validation rejects it), but NOT drop any table.
    """
    injection_name = "'; DROP TABLE inventory; --"
    payload = {"name": injection_name, "quantity": 1, "unit": "pcs"}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)

    # Should either create the item or reject it, but NOT crash
    assert response.status_code in (201, 400, 422)

    if response.status_code == 201:
        # The item was created safely with the injection string as the name
        assert response.json()["name"] == injection_name

    # Verify the inventory table still exists by listing items
    list_resp = client.get("/api/items", headers=AUTH_HEADERS)
    assert list_resp.status_code == 200


def test_sql_injection_in_customer_name(client):
    """SQL injection in customer name field."""
    injection_name = "Robert'; DROP TABLE customers;--"
    payload = {"name": injection_name, "customer_type": "retailer"}
    response = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code in (201, 400, 422)

    # Customers table still accessible
    list_resp = client.get("/api/customers", headers=AUTH_HEADERS)
    assert list_resp.status_code == 200


def test_sql_injection_in_supplier_name(client):
    """SQL injection in supplier name field."""
    injection_name = "Supplier' OR '1'='1"
    payload = {"name": injection_name}
    response = client.post("/api/suppliers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code in (201, 400, 422)

    list_resp = client.get("/api/suppliers", headers=AUTH_HEADERS)
    assert list_resp.status_code == 200


# ---------------------------------------------------------------------------
# XSS — API layer does not sanitise
# ---------------------------------------------------------------------------

def test_xss_in_customer_name_stored_as_is(client):
    """
    DOCUMENTED FINDING: The API stores XSS payloads as-is.
    No sanitisation in the API layer. Risk depends on frontend rendering.
    The frontend should escape HTML when displaying user content.
    """
    xss_name = "<script>alert(1)</script>"
    payload = {"name": xss_name, "customer_type": "retailer"}
    response = client.post("/api/customers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201

    data = response.json()
    # The script tag is stored verbatim in the database
    assert data["name"] == xss_name


def test_xss_in_item_name_stored_as_is(client):
    """XSS in item name is stored as-is."""
    xss_name = '<img src=x onerror=alert(1)>'
    payload = {"name": xss_name, "unit": "pcs"}
    response = client.post("/api/items", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    assert response.json()["name"] == xss_name


# ---------------------------------------------------------------------------
# Auth bypass — direct API call without session
# ---------------------------------------------------------------------------

def test_auth_bypass_no_headers(client):
    """Direct API call without session or key should redirect."""
    response = client.get("/api/items", follow_redirects=False)
    assert response.status_code in (302, 303, 307)


def test_auth_bypass_no_headers_post(client):
    """POST without auth should redirect."""
    response = client.post(
        "/api/items",
        json={"name": "Bypass Test"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)


# ---------------------------------------------------------------------------
# X-Internal-Key with empty string
# ---------------------------------------------------------------------------

def test_internal_key_empty_string_rejected(client):
    """
    When INTERNAL_API_KEY env var is set (non-empty), an empty string
    header should NOT grant access.
    """
    response = client.get(
        "/api/items",
        headers={"X-Internal-Key": ""},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303, 307)


def test_internal_key_none_header_rejected(client):
    """No X-Internal-Key header at all should not grant access."""
    response = client.get("/api/items", follow_redirects=False)
    assert response.status_code in (302, 303, 307)
