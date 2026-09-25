"""
Tests for payment tracking on sales bills — POST /api/bills (amount_paid),
GET/POST /api/bills/{id}/payments, PATCH /api/bills/{id}/payments/{id}/cancel.
"""
from tests.conftest import AUTH_HEADERS


def _bill_payload(item_id, quantity=2, unit_price=100.0, customer_name="Alice", **extra):
    payload = {
        "customer_name": customer_name,
        "customer_type": "retailer",
        "items": [{"item_id": item_id, "quantity": quantity, "unit_price": unit_price}],
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Default behavior (backward compatibility)
# ---------------------------------------------------------------------------

def test_bill_defaults_to_fully_paid(client, sample_item):
    """No amount_paid given -> behaves exactly as before: fully paid."""
    response = client.post("/api/bills", json=_bill_payload(sample_item.id, quantity=3, unit_price=100.0), headers=AUTH_HEADERS)
    data = response.json()

    assert response.status_code == 201
    assert data["amount_paid"] == data["total_amount"]
    assert data["balance_due"] == 0.0
    assert data["payment_status"] == "paid"


# ---------------------------------------------------------------------------
# Partial / credit sales
# ---------------------------------------------------------------------------

def test_bill_with_partial_payment(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=100.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    data = response.json()

    assert response.status_code == 201
    assert data["amount_paid"] == 100.0
    assert data["balance_due"] == round(data["total_amount"] - 100.0, 2)
    assert data["payment_status"] == "partially_paid"


def test_bill_with_zero_payment_is_unpaid(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=0.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    data = response.json()

    assert response.status_code == 201
    assert data["amount_paid"] == 0.0
    assert data["payment_status"] == "unpaid"


def test_bill_amount_paid_cannot_exceed_total(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=1, unit_price=100.0, amount_paid=999999.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 400
    assert "cannot exceed" in response.json()["detail"]


def test_bill_negative_amount_paid_rejected(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=1, unit_price=100.0, amount_paid=-10.0)
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_bill_invalid_payment_method_rejected(client, sample_item):
    payload = _bill_payload(sample_item.id, quantity=1, unit_price=100.0, payment_method="bitcoin")
    response = client.post("/api/bills", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Recording additional payments over time
# ---------------------------------------------------------------------------

def test_record_additional_payment_reduces_balance(client, sample_item):
    bill = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=100.0),
        headers=AUTH_HEADERS,
    ).json()
    balance = bill["balance_due"]

    resp = client.post(
        f"/api/bills/{bill['id']}/payments",
        json={"amount": balance, "payment_method": "upi", "reference_number": "TXN123"},
        headers=AUTH_HEADERS,
    )
    data = resp.json()

    assert resp.status_code == 201
    assert data["amount_paid"] == data["total_amount"]
    assert data["balance_due"] == 0.0
    assert data["payment_status"] == "paid"


def test_payment_exceeding_balance_rejected(client, sample_item):
    bill = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=100.0),
        headers=AUTH_HEADERS,
    ).json()

    resp = client.post(
        f"/api/bills/{bill['id']}/payments",
        json={"amount": bill["balance_due"] + 50.0},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    assert "exceed the outstanding balance" in resp.json()["detail"]


def test_zero_amount_payment_rejected(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()
    resp = client.post(f"/api/bills/{bill['id']}/payments", json={"amount": 0}, headers=AUTH_HEADERS)
    assert resp.status_code == 422


def test_cannot_pay_cancelled_bill(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()
    client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)

    resp = client.post(f"/api/bills/{bill['id']}/payments", json={"amount": 10.0}, headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()


def test_payment_status_is_cancelled_regardless_of_amount_paid(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id), headers=AUTH_HEADERS).json()  # fully paid
    client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)

    fetched = client.get(f"/api/bills/{bill['id']}", headers=AUTH_HEADERS).json()
    assert fetched["payment_status"] == "cancelled"


# ---------------------------------------------------------------------------
# Payment history / ledger
# ---------------------------------------------------------------------------

def test_get_payments_lists_history(client, sample_item):
    bill = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=100.0),
        headers=AUTH_HEADERS,
    ).json()
    client.post(f"/api/bills/{bill['id']}/payments", json={"amount": bill["balance_due"]}, headers=AUTH_HEADERS)

    payments = client.get(f"/api/bills/{bill['id']}/payments", headers=AUTH_HEADERS).json()
    assert len(payments) == 2
    assert payments[0]["amount"] == 100.0
    assert payments[0]["notes"] == "Recorded at sale"


def test_record_payment_with_backdated_payment_date(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()

    resp = client.post(
        f"/api/bills/{bill['id']}/payments",
        json={"amount": bill["total_amount"], "payment_date": "2026-01-15T10:00:00"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 201

    payments = client.get(f"/api/bills/{bill['id']}/payments", headers=AUTH_HEADERS).json()
    assert payments[0]["payment_date"].startswith("2026-01-15")


def test_get_payments_not_found_for_missing_bill(client):
    resp = client.get("/api/bills/999/payments", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_no_payment_recorded_when_bill_created_unpaid(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()
    payments = client.get(f"/api/bills/{bill['id']}/payments", headers=AUTH_HEADERS).json()
    assert payments == []


# ---------------------------------------------------------------------------
# Voiding a mistaken payment
# ---------------------------------------------------------------------------

def test_cancel_payment_reverses_balance(client, sample_item):
    bill = client.post(
        "/api/bills",
        json=_bill_payload(sample_item.id, quantity=3, unit_price=100.0, amount_paid=100.0),
        headers=AUTH_HEADERS,
    ).json()
    payments = client.get(f"/api/bills/{bill['id']}/payments", headers=AUTH_HEADERS).json()
    payment_id = payments[0]["id"]

    resp = client.patch(f"/api/bills/{bill['id']}/payments/{payment_id}/cancel", headers=AUTH_HEADERS)
    data = resp.json()

    assert resp.status_code == 200
    assert data["amount_paid"] == 0.0
    assert data["payment_status"] == "unpaid"


def test_cancel_payment_twice_rejected(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=50.0, quantity=1, unit_price=100.0), headers=AUTH_HEADERS).json()
    payment_id = client.get(f"/api/bills/{bill['id']}/payments", headers=AUTH_HEADERS).json()[0]["id"]

    client.patch(f"/api/bills/{bill['id']}/payments/{payment_id}/cancel", headers=AUTH_HEADERS)
    resp = client.patch(f"/api/bills/{bill['id']}/payments/{payment_id}/cancel", headers=AUTH_HEADERS)

    assert resp.status_code == 400
    assert "already cancelled" in resp.json()["detail"].lower()


def test_cancel_payment_not_found(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id), headers=AUTH_HEADERS).json()
    resp = client.patch(f"/api/bills/{bill['id']}/payments/999/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_cancel_payment_belonging_to_different_bill_rejected(client, sample_item):
    bill1 = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=50.0, quantity=1, unit_price=100.0), headers=AUTH_HEADERS).json()
    bill2 = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=50.0, quantity=1, unit_price=100.0), headers=AUTH_HEADERS).json()
    payment_of_bill1 = client.get(f"/api/bills/{bill1['id']}/payments", headers=AUTH_HEADERS).json()[0]["id"]

    resp = client.patch(f"/api/bills/{bill2['id']}/payments/{payment_of_bill1}/cancel", headers=AUTH_HEADERS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancelling a bill that still has money recorded against it
# ---------------------------------------------------------------------------

def test_cancel_paid_bill_warns_about_unreversed_payment(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id), headers=AUTH_HEADERS).json()  # fully paid
    resp = client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)
    data = resp.json()

    assert any("recorded as paid" in w for w in data["warnings"])


def test_cancel_unpaid_bill_has_no_payment_warning(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()
    resp = client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)
    data = resp.json()

    assert data["warnings"] == []


# ---------------------------------------------------------------------------
# Due date / overdue (opt-in only)
# ---------------------------------------------------------------------------

def test_bill_without_due_date_never_overdue(client, sample_item):
    bill = client.post("/api/bills", json=_bill_payload(sample_item.id, amount_paid=0.0), headers=AUTH_HEADERS).json()
    assert bill["due_date"] is None
    assert bill["payment_status"] == "unpaid"


def test_bill_with_past_due_date_and_balance_is_overdue(client, sample_item):
    payload = _bill_payload(sample_item.id, amount_paid=0.0, due_date="2020-01-01T00:00:00")
    bill = client.post("/api/bills", json=payload, headers=AUTH_HEADERS).json()
    assert bill["payment_status"] == "overdue"


def test_bill_with_future_due_date_is_not_overdue(client, sample_item):
    payload = _bill_payload(sample_item.id, amount_paid=0.0, due_date="2099-01-01T00:00:00")
    bill = client.post("/api/bills", json=payload, headers=AUTH_HEADERS).json()
    assert bill["payment_status"] == "unpaid"


def test_fully_paid_bill_with_past_due_date_is_not_overdue(client, sample_item):
    payload = _bill_payload(sample_item.id, due_date="2020-01-01T00:00:00")  # defaults to fully paid
    bill = client.post("/api/bills", json=payload, headers=AUTH_HEADERS).json()
    assert bill["payment_status"] == "paid"
