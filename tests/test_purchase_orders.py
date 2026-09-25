"""
Tests for the Purchase Order -> Goods Receipt flow.

PurchaseOrder (this file) never touches stock: it's the pre-commitment
step. Stock only changes when a PurchaseBill (goods receipt, tested in
test_purchases.py) is recorded — optionally against a PO via
purchase_order_id, validated and tracked here.
"""
from tests.conftest import AUTH_HEADERS


def _po_payload(item_id, quantity=20, unit_cost=15.0, supplier_name="Acme Supplies"):
    return {
        "supplier_name": supplier_name,
        "items": [{"item_id": item_id, "quantity": quantity, "unit_cost": unit_cost}],
    }


# ---------------------------------------------------------------------------
# Creating a PO never touches stock
# ---------------------------------------------------------------------------

def test_create_purchase_order_does_not_change_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    payload = _po_payload(sample_item.id, quantity=50)
    response = client.post("/api/purchase-orders", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert data["po_number"].startswith("PO-")
    assert data["status"] == "DRAFT"
    assert data["total_amount"] == 750.0  # 50 * 15.0

    db.refresh(sample_item)
    assert sample_item.quantity == original_qty


def test_create_purchase_order_no_items_rejected(client):
    response = client.post("/api/purchase-orders", json={"supplier_name": "X", "items": []}, headers=AUTH_HEADERS)
    assert response.status_code == 400


def test_create_purchase_order_unknown_item_rejected(client):
    response = client.post(
        "/api/purchase-orders",
        json={"supplier_name": "X", "items": [{"item_id": 9999, "quantity": 1, "unit_cost": 10}]},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 404


def test_purchase_order_auto_numbers_sequentially(client, sample_item):
    r1 = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS)
    r2 = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS)
    num1 = int(r1.json()["po_number"].split("-")[1])
    num2 = int(r2.json()["po_number"].split("-")[1])
    assert num2 == num1 + 1


# ---------------------------------------------------------------------------
# Lifecycle: DRAFT -> CONFIRMED -> CANCELLED
# ---------------------------------------------------------------------------

def test_confirm_draft_order(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    resp = client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CONFIRMED"


def test_confirm_already_confirmed_order_rejected(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_cancel_draft_order(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    resp = client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cancel_confirmed_order(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"


def test_cannot_cancel_order_already_cancelled(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_get_nonexistent_order_404(client):
    resp = client.get("/api/purchase-orders/999", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_get_purchase_order_by_id(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS).json()
    resp = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert resp.json()["po_number"] == order["po_number"]


def test_list_purchase_orders(client, sample_item):
    client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS)
    client.post("/api/purchase-orders", json=_po_payload(sample_item.id), headers=AUTH_HEADERS)
    resp = client.get("/api/purchase-orders", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# Receiving goods against a DRAFT order is rejected (not yet committed)
# ---------------------------------------------------------------------------

def test_cannot_receive_against_draft_order(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 20, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "draft" in resp.json()["detail"].lower()


def test_cannot_receive_against_cancelled_order(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 20, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400


def test_receiving_against_nonexistent_order_404(client, sample_item):
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": 999,
              "items": [{"item_id": sample_item.id, "quantity": 1, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Full receipt in one go: CONFIRMED -> RECEIVED
# ---------------------------------------------------------------------------

def test_full_receipt_marks_order_received_and_increases_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    receipt = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 20, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert receipt.status_code == 201
    assert receipt.json()["purchase_order_id"] == order["id"]

    db.refresh(sample_item)
    assert sample_item.quantity == original_qty + 20

    order_after = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after["status"] == "RECEIVED"
    assert order_after["items"][0]["quantity_received"] == 20


# ---------------------------------------------------------------------------
# Partial receipt: CONFIRMED -> PARTIALLY_RECEIVED -> RECEIVED
# ---------------------------------------------------------------------------

def test_partial_receipt_marks_order_partially_received(client, db, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 12, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )

    order_after = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after["status"] == "PARTIALLY_RECEIVED"
    assert order_after["items"][0]["quantity_received"] == 12


def test_second_partial_receipt_completes_order(client, db, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 12, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    # second receipt can be recorded against the now-PARTIALLY_RECEIVED order
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 8, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201

    order_after = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after["status"] == "RECEIVED"
    assert order_after["items"][0]["quantity_received"] == 20


def test_receiving_more_than_remaining_rejected(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 15, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    # only 5 remain — asking for 6 must be rejected
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 6, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "only 5 remaining" in resp.json()["detail"]


def test_over_receiving_in_a_single_call_rejected(client, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 21, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400


def test_receiving_item_not_on_the_order_is_allowed_but_untracked(client, db, sample_item, sample_item_b):
    """A supplier substitution / extra item not on the PO shouldn't block
    the whole receipt — it's just not validated against that PO's lines."""
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    resp = client.post(
        "/api/purchases",
        json={
            "supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
            "items": [
                {"item_id": sample_item.id, "quantity": 20, "unit_cost": 15.0},
                {"item_id": sample_item_b.id, "quantity": 5, "unit_cost": 10.0},
            ],
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Cancelling a receipt reverses the PO's received-quantity tracking too
# ---------------------------------------------------------------------------

def test_cancelling_receipt_reverses_po_tracking(client, db, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    receipt = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 20, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    ).json()

    order_after_receipt = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after_receipt["status"] == "RECEIVED"

    cancel_resp = client.patch(f"/api/purchases/{receipt['id']}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200

    order_after_cancel = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after_cancel["status"] == "CONFIRMED"
    assert order_after_cancel["items"][0]["quantity_received"] == 0


def test_cancelling_partial_receipt_reverts_to_partially_received(client, db, sample_item):
    order = client.post("/api/purchase-orders", json=_po_payload(sample_item.id, quantity=20), headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchase-orders/{order['id']}/confirm", headers=AUTH_HEADERS)

    receipt1 = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 10, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    ).json()
    receipt2 = client.post(
        "/api/purchases",
        json={"supplier_name": "Acme Supplies", "purchase_order_id": order["id"],
              "items": [{"item_id": sample_item.id, "quantity": 10, "unit_cost": 15.0}]},
        headers=AUTH_HEADERS,
    ).json()

    assert client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()["status"] == "RECEIVED"

    client.patch(f"/api/purchases/{receipt2['id']}/cancel", headers=AUTH_HEADERS)

    order_after = client.get(f"/api/purchase-orders/{order['id']}", headers=AUTH_HEADERS).json()
    assert order_after["status"] == "PARTIALLY_RECEIVED"
    assert order_after["items"][0]["quantity_received"] == 10


# ---------------------------------------------------------------------------
# Direct receipts (no PO) are completely unaffected
# ---------------------------------------------------------------------------

def test_direct_receipt_without_po_still_works(client, db, sample_item):
    """The pre-existing simplified flow (no purchase order) must be
    completely unchanged."""
    original_qty = sample_item.quantity
    resp = client.post(
        "/api/purchases",
        json={"supplier_name": "Walk-in Supplier", "items": [{"item_id": sample_item.id, "quantity": 10, "unit_cost": 5.0}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    assert resp.json()["purchase_order_id"] is None

    db.refresh(sample_item)
    assert sample_item.quantity == original_qty + 10
