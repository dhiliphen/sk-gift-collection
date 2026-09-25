"""
Tests for purchase returns / debit notes — POST/GET /api/purchases/{id}/returns,
PATCH .../returns/{id}/cancel.

Symmetric to sales returns: the original PurchaseBill is never mutated;
stock decreases (goods physically leave for the supplier), which is only
possible while that stock is still on hand.
"""
from tests.conftest import AUTH_HEADERS


def _purchase_payload(item_id, quantity=10, unit_cost=15.0, supplier_name="Supplier X"):
    return {
        "supplier_name": supplier_name,
        "items": [{"item_id": item_id, "quantity": quantity, "unit_cost": unit_cost}],
    }


def _create_purchase(client, item_id, quantity=10, unit_cost=15.0):
    return client.post("/api/purchases", json=_purchase_payload(item_id, quantity, unit_cost), headers=AUTH_HEADERS).json()


# ---------------------------------------------------------------------------
# Creating a return
# ---------------------------------------------------------------------------

def test_create_return_decreases_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    db.refresh(sample_item)
    after_purchase_qty = sample_item.quantity
    assert after_purchase_qty == original_qty + 10

    purchase_item_id = purchase["items"][0]["id"]
    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"reason": "Wrong item shipped", "items": [{"purchase_item_id": purchase_item_id, "quantity": 4}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["debit_note_number"].startswith("DN-")
    assert data["status"] == "issued"
    assert data["purchase_id"] == purchase["id"]
    assert data["total_amount"] == 60.0  # 4 * 15.0

    db.refresh(sample_item)
    assert sample_item.quantity == after_purchase_qty - 4


def test_original_purchase_is_never_modified_by_a_return(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]

    client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 4}]},
        headers=AUTH_HEADERS,
    )

    refetched = client.get(f"/api/purchases/{purchase['id']}", headers=AUTH_HEADERS).json()
    assert refetched["total_amount"] == purchase["total_amount"]
    assert refetched["status"] == purchase["status"]


def test_return_no_items_rejected(client, sample_item):
    purchase = _create_purchase(client, sample_item.id)
    resp = client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": []}, headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_return_from_nonexistent_purchase_404(client):
    resp = client.post("/api/purchases/999/returns", json={"items": [{"purchase_item_id": 1, "quantity": 1}]}, headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_return_unknown_purchase_line_404(client, sample_item):
    purchase = _create_purchase(client, sample_item.id)
    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": 9999, "quantity": 1}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_cannot_return_from_cancelled_purchase(client, sample_item):
    purchase = _create_purchase(client, sample_item.id)
    client.patch(f"/api/purchases/{purchase['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": purchase["items"][0]["id"], "quantity": 1}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()


def test_return_auto_numbers_sequentially(client, sample_item):
    p1 = _create_purchase(client, sample_item.id, quantity=10)
    p2 = _create_purchase(client, sample_item.id, quantity=10)
    r1 = client.post(f"/api/purchases/{p1['id']}/returns", json={"items": [{"purchase_item_id": p1["items"][0]["id"], "quantity": 1}]}, headers=AUTH_HEADERS).json()
    r2 = client.post(f"/api/purchases/{p2['id']}/returns", json={"items": [{"purchase_item_id": p2["items"][0]["id"], "quantity": 1}]}, headers=AUTH_HEADERS).json()
    num1 = int(r1["debit_note_number"].split("-")[1])
    num2 = int(r2["debit_note_number"].split("-")[1])
    assert num2 == num1 + 1


# ---------------------------------------------------------------------------
# Over-return / duplicate-line aggregation guard
# ---------------------------------------------------------------------------

def test_cannot_return_more_than_purchased(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": purchase["items"][0]["id"], "quantity": 11}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "only 10 remaining" in resp.json()["detail"]


def test_duplicate_lines_in_one_return_are_aggregated(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [
            {"purchase_item_id": purchase_item_id, "quantity": 6},
            {"purchase_item_id": purchase_item_id, "quantity": 6},
        ]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "only 10 remaining" in resp.json()["detail"]


def test_cannot_return_more_than_currently_in_stock(client, db, sample_item):
    """The purchased stock has since been sold off — physically nothing
    left to send back to the supplier."""
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    # sell off 8 of the 10 just purchased, plus whatever was already there
    db.refresh(sample_item)
    client.patch(f"/api/items/{sample_item.id}/stock", json={"quantity_change": -(sample_item.quantity - 3)}, headers=AUTH_HEADERS)

    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": purchase["items"][0]["id"], "quantity": 5}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "currently in stock" in resp.json()["detail"]


def test_partial_returns_accumulate_against_the_cap(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]

    client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 6}]}, headers=AUTH_HEADERS)
    ok = client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 4}]}, headers=AUTH_HEADERS)
    assert ok.status_code == 201

    over = client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)
    assert over.status_code == 400
    assert "only 0 remaining" in over.json()["detail"]


def test_purchase_item_shows_updated_quantity_returned(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 3}]}, headers=AUTH_HEADERS)

    refetched = client.get(f"/api/purchases/{purchase['id']}", headers=AUTH_HEADERS).json()
    assert refetched["items"][0]["quantity_returned"] == 3


# ---------------------------------------------------------------------------
# Listing returns
# ---------------------------------------------------------------------------

def test_get_purchase_returns_lists_history(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)
    client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)

    returns = client.get(f"/api/purchases/{purchase['id']}/returns", headers=AUTH_HEADERS).json()
    assert len(returns) == 2


def test_get_returns_for_purchase_with_none_is_empty(client, sample_item):
    purchase = _create_purchase(client, sample_item.id)
    assert client.get(f"/api/purchases/{purchase['id']}/returns", headers=AUTH_HEADERS).json() == []


# ---------------------------------------------------------------------------
# Deleted-item warning
# ---------------------------------------------------------------------------

def test_return_warns_when_item_deleted_from_inventory(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    client.delete(f"/api/items/{sample_item.id}", headers=AUTH_HEADERS)

    resp = client.post(
        f"/api/purchases/{purchase['id']}/returns",
        json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 2}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    assert len(resp.json()["warnings"]) == 1
    assert "deleted" in resp.json()["warnings"][0].lower()


# ---------------------------------------------------------------------------
# Cancelling (voiding) a return
# ---------------------------------------------------------------------------

def test_cancel_return_restores_stock_and_tracking(client, db, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    ret = client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 4}]}, headers=AUTH_HEADERS).json()

    db.refresh(sample_item)
    qty_after_return = sample_item.quantity

    cancel_resp = client.patch(f"/api/purchases/{purchase['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    db.refresh(sample_item)
    assert sample_item.quantity == qty_after_return + 4

    refetched_purchase = client.get(f"/api/purchases/{purchase['id']}", headers=AUTH_HEADERS).json()
    assert refetched_purchase["items"][0]["quantity_returned"] == 0


def test_cancel_already_cancelled_return_rejected(client, sample_item):
    purchase = _create_purchase(client, sample_item.id, quantity=10)
    purchase_item_id = purchase["items"][0]["id"]
    ret = client.post(f"/api/purchases/{purchase['id']}/returns", json={"items": [{"purchase_item_id": purchase_item_id, "quantity": 4}]}, headers=AUTH_HEADERS).json()
    client.patch(f"/api/purchases/{purchase['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/purchases/{purchase['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_cancel_return_not_found(client, sample_item):
    purchase = _create_purchase(client, sample_item.id)
    resp = client.patch(f"/api/purchases/{purchase['id']}/returns/999/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 404
