"""
Tests for the User/role model, the audit log, and the one place RBAC is
actually enforced in this app: viewing the audit trail is ADMIN-only.
Per the spec's own caution ("do not implement unnecessary permissions if
the application only has one user"), role checks are NOT retrofitted onto
every existing endpoint — see app/auth.py's require_role().
"""
from tests.conftest import AUTH_HEADERS, ADMIN_USERNAME, ADMIN_PASSWORD, login_as


def _audit_actions(client, cookies=None, headers=None):
    resp = client.get("/api/audit-log", cookies=cookies, headers=headers or {})
    return resp


# ---------------------------------------------------------------------------
# Login / logout audit trail
# ---------------------------------------------------------------------------

def test_login_success_is_audited(client):
    login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.get("/api/audit-log", headers=AUTH_HEADERS)
    actions = [a["action"] for a in resp.json()]
    assert "LOGIN_SUCCESS" in actions


def test_login_failure_is_audited_without_password(client):
    client.post("/login", data={"username": "admin", "password": "wrongpassword"}, follow_redirects=False)
    resp = client.get("/api/audit-log", headers=AUTH_HEADERS)
    entries = resp.json()
    failure = next(e for e in entries if e["action"] == "LOGIN_FAILURE")
    assert "wrongpassword" not in (failure["new_value"] or "")
    assert "attempted_username" in failure["new_value"]


def test_logout_is_audited(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    client.post("/logout", cookies=cookies)
    resp = client.get("/api/audit-log", headers=AUTH_HEADERS)
    actions = [a["action"] for a in resp.json()]
    assert "LOGOUT" in actions


# ---------------------------------------------------------------------------
# RBAC: audit log is ADMIN-only
# ---------------------------------------------------------------------------

def test_admin_can_view_audit_log(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.get("/api/audit-log", cookies=cookies)
    assert resp.status_code == 200


def test_viewer_cannot_view_audit_log(client, sample_viewer_user):
    cookies = login_as(client, "viewer1", "viewerpass123")
    resp = client.get("/api/audit-log", cookies=cookies)
    assert resp.status_code == 403


def test_internal_service_calls_bypass_role_check(client):
    """X-Internal-Key requests are trusted system calls with no human user
    to check a role against — they must not be blocked by require_role."""
    resp = client.get("/api/audit-log", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_viewer_cannot_create_users(client, sample_viewer_user):
    cookies = login_as(client, "viewer1", "viewerpass123")
    resp = client.post(
        "/api/users", json={"username": "newperson", "password": "somepassword"}, cookies=cookies,
    )
    assert resp.status_code == 403


def test_admin_can_create_user(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.post(
        "/api/users",
        json={"username": "salesperson1", "password": "salespass123", "role": "SALES"},
        cookies=cookies,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "salesperson1"
    assert data["role"] == "SALES"
    assert "password" not in data
    assert "password_hash" not in data


def test_new_user_defaults_to_viewer_role(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.post("/api/users", json={"username": "person2", "password": "password123"}, cookies=cookies)
    assert resp.json()["role"] == "VIEWER"


def test_duplicate_username_rejected(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    client.post("/api/users", json={"username": "dupe", "password": "password123"}, cookies=cookies)
    resp = client.post("/api/users", json={"username": "dupe", "password": "password456"}, cookies=cookies)
    assert resp.status_code == 400


def test_new_user_can_log_in(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    client.post(
        "/api/users", json={"username": "newlogin", "password": "newloginpass", "role": "MANAGER"}, cookies=cookies,
    )
    login_cookies = login_as(client, "newlogin", "newloginpass")
    assert login_cookies["session"] is not None

    resp = client.get("/api/items", cookies=login_cookies)
    assert resp.status_code == 200


def test_me_returns_current_user(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.get("/api/users/me", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == ADMIN_USERNAME
    assert data["role"] == "ADMIN"
    assert "password_hash" not in data


def test_me_without_session_is_unauthorized(client):
    resp = client.get("/api/users/me", headers=AUTH_HEADERS)
    assert resp.status_code == 401


def test_admin_can_list_users(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.get("/api/users", cookies=cookies)
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert ADMIN_USERNAME in usernames


def test_get_nonexistent_user_404(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    resp = client.put("/api/users/999", json={"role": "VIEWER"}, cookies=cookies)
    assert resp.status_code == 404


def test_admin_can_change_user_password(client):
    admin_cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    created = client.post(
        "/api/users", json={"username": "passchange", "password": "oldpassword"}, cookies=admin_cookies,
    ).json()

    client.put(f"/api/users/{created['id']}", json={"password": "newpassword123"}, cookies=admin_cookies)

    old_login = client.post("/login", data={"username": "passchange", "password": "oldpassword"}, follow_redirects=False)
    assert old_login.status_code == 401

    new_login_cookies = login_as(client, "passchange", "newpassword123")
    assert new_login_cookies["session"] is not None


def test_deactivated_user_cannot_log_in(client):
    admin_cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    created = client.post(
        "/api/users", json={"username": "tobedisabled", "password": "somepassword"}, cookies=admin_cookies,
    ).json()

    client.put(f"/api/users/{created['id']}", json={"is_active": False}, cookies=admin_cookies)

    resp = client.post("/login", data={"username": "tobedisabled", "password": "somepassword"}, follow_redirects=False)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Audit trail content for business actions
# ---------------------------------------------------------------------------

def test_create_item_is_audited(client):
    client.post("/api/items", json={"name": "Audited Widget", "quantity": 5, "selling_price": 100}, headers=AUTH_HEADERS)
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CREATE_ITEM")
    assert entry["entity_type"] == "item"
    assert "Audited Widget" in entry["new_value"]


def test_update_item_records_old_and_new_values(client):
    item = client.post("/api/items", json={"name": "Editable Widget", "selling_price": 50}, headers=AUTH_HEADERS).json()
    client.put(f"/api/items/{item['id']}", json={"selling_price": 75}, headers=AUTH_HEADERS)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "UPDATE_ITEM" and e["entity_id"] == item["id"])
    assert "50" in entry["old_value"]
    assert "75" in entry["new_value"]


def test_delete_item_records_old_value(client):
    item = client.post("/api/items", json={"name": "Doomed Widget"}, headers=AUTH_HEADERS).json()
    client.delete(f"/api/items/{item['id']}", headers=AUTH_HEADERS)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "DELETE_ITEM" and e["entity_id"] == item["id"])
    assert "Doomed Widget" in entry["old_value"]


def test_create_invoice_is_audited(client, sample_item):
    bill = client.post(
        "/api/bills",
        json={"customer_name": "Audit Test", "customer_type": "retailer",
              "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}]},
        headers=AUTH_HEADERS,
    ).json()
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CREATE_INVOICE" and e["entity_id"] == bill["id"])
    assert entry["entity_type"] == "bill"


def test_cancel_invoice_is_audited(client, sample_item):
    bill = client.post(
        "/api/bills",
        json={"customer_name": "Audit Test", "customer_type": "retailer",
              "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}]},
        headers=AUTH_HEADERS,
    ).json()
    client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CANCEL_INVOICE" and e["entity_id"] == bill["id"])
    assert '"status": "paid"' in entry["old_value"] or "paid" in entry["old_value"]
    assert "cancelled" in entry["new_value"]


def test_create_purchase_is_audited(client, sample_item):
    purchase = client.post(
        "/api/purchases",
        json={"supplier_name": "Audit Supplier", "items": [{"item_id": sample_item.id, "quantity": 5, "unit_cost": 10.0}]},
        headers=AUTH_HEADERS,
    ).json()
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CREATE_PURCHASE" and e["entity_id"] == purchase["id"])
    assert entry["entity_type"] == "purchase"


def test_stock_adjustment_is_audited(client, sample_item):
    client.patch(f"/api/items/{sample_item.id}/stock", json={"quantity_change": 5}, headers=AUTH_HEADERS)
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "STOCK_ADJUSTMENT" and e["entity_id"] == sample_item.id)
    assert entry["old_value"] is not None
    assert entry["new_value"] is not None


def test_create_customer_is_audited(client):
    client.post("/api/customers", json={"name": "Audited Customer", "customer_type": "retailer"}, headers=AUTH_HEADERS)
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    assert any(e["action"] == "CREATE_CUSTOMER" for e in entries)


def test_create_supplier_is_audited(client):
    client.post("/api/suppliers", json={"name": "Audited Supplier"}, headers=AUTH_HEADERS)
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    assert any(e["action"] == "CREATE_SUPPLIER" for e in entries)


def test_record_payment_is_audited(client, sample_item):
    bill = client.post(
        "/api/bills",
        json={"customer_name": "Pay Audit", "customer_type": "retailer",
              "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 100.0}], "amount_paid": 0},
        headers=AUTH_HEADERS,
    ).json()
    client.post(f"/api/bills/{bill['id']}/payments", json={"amount": 50}, headers=AUTH_HEADERS)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CREATE_PAYMENT" and e["entity_id"] == bill["id"])
    assert "50" in entry["new_value"]


def test_create_purchase_order_is_audited(client, sample_item):
    order = client.post(
        "/api/purchase-orders",
        json={"supplier_name": "Audit PO Supplier", "items": [{"item_id": sample_item.id, "quantity": 5, "unit_cost": 10.0}]},
        headers=AUTH_HEADERS,
    ).json()
    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    entry = next(e for e in entries if e["action"] == "CREATE_PURCHASE_ORDER" and e["entity_id"] == order["id"])
    assert entry["entity_type"] == "purchase_order"


def test_confirm_and_cancel_purchase_order_are_audited(client, sample_item):
    order = client.post(
        "/api/purchase-orders",
        json={"supplier_name": "Audit PO Supplier2", "items": [{"item_id": sample_item.id, "quantity": 5, "unit_cost": 10.0}]},
        headers=AUTH_HEADERS,
    ).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)
    client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    actions = [e["action"] for e in entries if e["entity_id"] == order["id"]]
    assert "CONFIRM_PURCHASE_ORDER" in actions
    assert "CANCEL_PURCHASE_ORDER" in actions


def test_audit_log_can_filter_by_action(client):
    client.post("/api/items", json={"name": "Filter Test Item"}, headers=AUTH_HEADERS)
    resp = client.get("/api/audit-log?action=CREATE_ITEM", headers=AUTH_HEADERS)
    entries = resp.json()
    assert len(entries) >= 1
    assert all(e["action"] == "CREATE_ITEM" for e in entries)


def test_audit_log_never_contains_password_hash(client):
    cookies = login_as(client, ADMIN_USERNAME, ADMIN_PASSWORD)
    client.post("/api/users", json={"username": "secure1", "password": "supersecretpassword"}, cookies=cookies)

    entries = client.get("/api/audit-log", headers=AUTH_HEADERS).json()
    for e in entries:
        blob = (e["old_value"] or "") + (e["new_value"] or "")
        assert "password_hash" not in blob
        assert "supersecretpassword" not in blob
