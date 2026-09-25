"""
Tests for sales returns / credit notes — POST/GET /api/bills/{id}/returns,
PATCH .../returns/{id}/cancel.

Design decision under test: the original Bill is never mutated by a return
(total_amount, amount_paid, payment_state all stay exactly as they were).
A return only increases stock and produces a standalone credit note record
— how the credited value gets settled is left to the business owner.
"""
from tests.conftest import AUTH_HEADERS


def _bill_payload(item_id, quantity=2, unit_price=100.0, customer_name="Alice"):
    return {
        "customer_name": customer_name,
        "customer_type": "retailer",
        "items": [{"item_id": item_id, "quantity": quantity, "unit_price": unit_price}],
    }


def _create_bill(client, item_id, quantity=5, unit_price=100.0):
    return client.post("/api/bills", json=_bill_payload(item_id, quantity, unit_price), headers=AUTH_HEADERS).json()


# ---------------------------------------------------------------------------
# Creating a return
# ---------------------------------------------------------------------------

def test_create_return_increases_stock(client, db, sample_item):
    original_qty = sample_item.quantity
    bill = _create_bill(client, sample_item.id, quantity=5)
    db.refresh(sample_item)
    after_sale_qty = sample_item.quantity
    assert after_sale_qty == original_qty - 5

    bill_item_id = bill["items"][0]["id"]
    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"reason": "Damaged", "items": [{"bill_item_id": bill_item_id, "quantity": 2}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["credit_note_number"].startswith("CRN-")
    assert data["status"] == "issued"
    assert data["bill_id"] == bill["id"]

    db.refresh(sample_item)
    assert sample_item.quantity == after_sale_qty + 2


def test_return_computes_taxable_and_tax_from_original_line(client, db, sample_item):
    """gst_rate on sample_item is 18%."""
    bill = _create_bill(client, sample_item.id, quantity=5, unit_price=100.0)
    bill_item_id = bill["items"][0]["id"]

    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]},
        headers=AUTH_HEADERS,
    )
    data = resp.json()
    assert data["taxable_amount"] == 200.0   # 2 * 100
    assert data["igst_amount"] == 36.0       # 200 * 18%
    assert data["total_amount"] == 236.0


def test_original_bill_is_never_modified_by_a_return(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5, unit_price=100.0)
    bill_item_id = bill["items"][0]["id"]

    client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]},
        headers=AUTH_HEADERS,
    )

    refetched = client.get(f"/api/bills/{bill['id']}", headers=AUTH_HEADERS).json()
    assert refetched["total_amount"] == bill["total_amount"]
    assert refetched["amount_paid"] == bill["amount_paid"]
    assert refetched["payment_status"] == bill["payment_status"]
    assert refetched["status"] == bill["status"]


def test_return_no_items_rejected(client, sample_item):
    bill = _create_bill(client, sample_item.id)
    resp = client.post(f"/api/bills/{bill['id']}/returns", json={"items": []}, headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_return_from_nonexistent_bill_404(client):
    resp = client.post("/api/bills/999/returns", json={"items": [{"bill_item_id": 1, "quantity": 1}]}, headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_return_unknown_bill_line_404(client, sample_item):
    bill = _create_bill(client, sample_item.id)
    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": 9999, "quantity": 1}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def test_cannot_return_from_cancelled_bill(client, sample_item):
    bill = _create_bill(client, sample_item.id)
    client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": bill["items"][0]["id"], "quantity": 1}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()


def test_return_auto_numbers_sequentially(client, sample_item):
    bill1 = _create_bill(client, sample_item.id, quantity=5)
    bill2 = _create_bill(client, sample_item.id, quantity=5)
    r1 = client.post(f"/api/bills/{bill1['id']}/returns", json={"items": [{"bill_item_id": bill1["items"][0]["id"], "quantity": 1}]}, headers=AUTH_HEADERS).json()
    r2 = client.post(f"/api/bills/{bill2['id']}/returns", json={"items": [{"bill_item_id": bill2["items"][0]["id"], "quantity": 1}]}, headers=AUTH_HEADERS).json()
    num1 = int(r1["credit_note_number"].split("-")[1])
    num2 = int(r2["credit_note_number"].split("-")[1])
    assert num2 == num1 + 1


# ---------------------------------------------------------------------------
# Over-return / duplicate-line aggregation guard
# ---------------------------------------------------------------------------

def test_cannot_return_more_than_billed(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": bill["items"][0]["id"], "quantity": 6}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "only 5 remaining" in resp.json()["detail"]


def test_duplicate_lines_in_one_return_are_aggregated(client, sample_item):
    """Two lines for the same bill_item_id in a single return request must
    be validated against their combined total — the exact bug class fixed
    for bill creation earlier in this project."""
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [
            {"bill_item_id": bill_item_id, "quantity": 3},
            {"bill_item_id": bill_item_id, "quantity": 3},
        ]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "only 5 remaining" in resp.json()["detail"]


def test_partial_returns_accumulate_against_the_cap(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]

    client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 3}]}, headers=AUTH_HEADERS)
    # only 2 remain
    ok = client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]}, headers=AUTH_HEADERS)
    assert ok.status_code == 201

    over = client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)
    assert over.status_code == 400
    assert "only 0 remaining" in over.json()["detail"]


def test_bill_item_shows_updated_quantity_returned(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]}, headers=AUTH_HEADERS)

    refetched = client.get(f"/api/bills/{bill['id']}", headers=AUTH_HEADERS).json()
    assert refetched["items"][0]["quantity_returned"] == 2


# ---------------------------------------------------------------------------
# Listing returns for a bill
# ---------------------------------------------------------------------------

def test_get_bill_returns_lists_history(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)
    client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 1}]}, headers=AUTH_HEADERS)

    returns = client.get(f"/api/bills/{bill['id']}/returns", headers=AUTH_HEADERS).json()
    assert len(returns) == 2


def test_get_returns_for_bill_with_none_is_empty(client, sample_item):
    bill = _create_bill(client, sample_item.id)
    assert client.get(f"/api/bills/{bill['id']}/returns", headers=AUTH_HEADERS).json() == []


# ---------------------------------------------------------------------------
# Deleted-item warning (mirrors AMB-003 pattern for cancellation)
# ---------------------------------------------------------------------------

def test_return_warns_when_item_deleted_from_inventory(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    client.delete(f"/api/items/{sample_item.id}", headers=AUTH_HEADERS)

    resp = client.post(
        f"/api/bills/{bill['id']}/returns",
        json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201
    assert len(resp.json()["warnings"]) == 1
    assert "deleted" in resp.json()["warnings"][0].lower()


# ---------------------------------------------------------------------------
# Cancelling (voiding) a return
# ---------------------------------------------------------------------------

def test_cancel_return_reverses_stock_and_tracking(client, db, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    ret = client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]}, headers=AUTH_HEADERS).json()

    db.refresh(sample_item)
    qty_after_return = sample_item.quantity

    cancel_resp = client.patch(f"/api/bills/{bill['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    db.refresh(sample_item)
    assert sample_item.quantity == qty_after_return - 2

    refetched_bill = client.get(f"/api/bills/{bill['id']}", headers=AUTH_HEADERS).json()
    assert refetched_bill["items"][0]["quantity_returned"] == 0


def test_cancel_already_cancelled_return_rejected(client, sample_item):
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    ret = client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]}, headers=AUTH_HEADERS).json()
    client.patch(f"/api/bills/{bill['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/bills/{bill['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_cancel_return_blocked_if_stock_resold(client, db, sample_item):
    """The returned stock was sold again before the return could be
    voided — mirrors the existing purchase-cancel-after-consumption guard."""
    bill = _create_bill(client, sample_item.id, quantity=5)
    bill_item_id = bill["items"][0]["id"]
    ret = client.post(f"/api/bills/{bill['id']}/returns", json={"items": [{"bill_item_id": bill_item_id, "quantity": 2}]}, headers=AUTH_HEADERS).json()

    # Drain stock down to less than the 2 units this return would need to
    # remove on cancellation (as if it had been sold again since).
    db.refresh(sample_item)
    client.patch(
        f"/api/items/{sample_item.id}/stock",
        json={"quantity_change": -(sample_item.quantity - 1)},
        headers=AUTH_HEADERS,
    )

    resp = client.patch(f"/api/bills/{bill['id']}/returns/{ret['id']}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 409


def test_cancel_return_not_found(client, sample_item):
    bill = _create_bill(client, sample_item.id)
    resp = client.patch(f"/api/bills/{bill['id']}/returns/999/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 404
