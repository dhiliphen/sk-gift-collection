"""
Tests for GET /api/dashboard — cross-domain business snapshot (today's
sales/purchases/payments/outstanding, inventory health, recent activity,
alerts). See app/services/dashboard.py.
"""
from tests.conftest import AUTH_HEADERS


def test_dashboard_empty_state(client):
    response = client.get("/api/dashboard", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()

    assert data["today"] == {
        "sales_amount": 0, "purchases_amount": 0,
        "payments_received": 0, "outstanding_amount": 0,
    }
    assert data["inventory"]["total_products"] == 0
    assert data["sales"]["invoices_today"] == 0
    assert data["sales"]["recent_invoices"] == []
    assert data["purchases"]["recent_purchases"] == []
    assert data["alerts"] == []


def test_dashboard_today_sales_and_payments(client, sample_item):
    client.post(
        "/api/bills",
        json={
            "customer_name": "Bob", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 2, "unit_price": 100.0}],
            "amount_paid": 50.0,
        },
        headers=AUTH_HEADERS,
    )
    response = client.get("/api/dashboard", headers=AUTH_HEADERS)
    data = response.json()

    assert data["today"]["sales_amount"] == 236.0  # 200 taxable + 18% gst
    assert data["today"]["payments_received"] == 50.0
    assert data["today"]["outstanding_amount"] == 186.0
    assert data["sales"]["invoices_today"] == 1
    assert data["sales"]["pending_payment_count"] == 1
    assert len(data["sales"]["recent_invoices"]) == 1


def test_dashboard_excludes_cancelled_bill_from_today_sales(client, sample_item):
    bill = client.post(
        "/api/bills",
        json={
            "customer_name": "Bob", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 100.0}],
        },
        headers=AUTH_HEADERS,
    ).json()
    client.patch(f"/api/bills/{bill['id']}/cancel", headers=AUTH_HEADERS)

    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    assert data["today"]["sales_amount"] == 0
    assert data["today"]["outstanding_amount"] == 0


def test_dashboard_today_purchases(client, sample_item):
    client.post(
        "/api/purchases",
        json={"supplier_name": "Acme", "items": [{"item_id": sample_item.id, "quantity": 5, "unit_cost": 10.0}]},
        headers=AUTH_HEADERS,
    )
    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    assert data["today"]["purchases_amount"] == 50.0
    assert len(data["purchases"]["recent_purchases"]) == 1


def test_dashboard_inventory_counts(client, db):
    from app import models
    db.add_all([
        models.Item(name="Healthy", quantity=100, low_stock_threshold=10, cost_price=5, unit="pcs"),
        models.Item(name="Low", quantity=3, low_stock_threshold=10, cost_price=5, unit="pcs"),
        models.Item(name="Zero", quantity=0, low_stock_threshold=10, cost_price=5, unit="pcs"),
    ])
    db.commit()

    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    assert data["inventory"]["total_products"] == 3
    assert data["inventory"]["low_stock_count"] == 2  # Low + Zero (<=threshold)
    assert data["inventory"]["out_of_stock_count"] == 1  # Zero only


def test_dashboard_alerts_for_low_and_out_of_stock(client, db):
    from app import models
    db.add(models.Item(name="Zero", quantity=0, low_stock_threshold=10, unit="pcs"))
    db.commit()

    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    messages = [a["message"] for a in data["alerts"]]
    assert any("below minimum stock" in m for m in messages)
    assert any("out of stock" in m for m in messages)


def test_dashboard_overdue_alert_and_count(client, sample_item):
    client.post(
        "/api/bills",
        json={
            "customer_name": "Bob", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 100.0}],
            "amount_paid": 0.0,
            "due_date": "2020-01-01T00:00:00",
        },
        headers=AUTH_HEADERS,
    )
    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    messages = [a["message"] for a in data["alerts"]]
    assert any("overdue" in m for m in messages)


def test_dashboard_no_overdue_alert_without_due_date(client, sample_item):
    """Bills with no due_date must never count as overdue (opt-in only)."""
    client.post(
        "/api/bills",
        json={
            "customer_name": "Bob", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 100.0}],
            "amount_paid": 0.0,
        },
        headers=AUTH_HEADERS,
    )
    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    messages = [a["message"] for a in data["alerts"]]
    assert not any("overdue" in m for m in messages)


def test_dashboard_recent_invoices_capped_at_five(client, sample_item):
    for _ in range(7):
        client.post(
            "/api/bills",
            json={
                "customer_name": "Bob", "customer_type": "retailer",
                "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 10.0}],
            },
            headers=AUTH_HEADERS,
        )
    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    assert len(data["sales"]["recent_invoices"]) == 5
    # newest first
    numbers = [inv["invoice_number"] for inv in data["sales"]["recent_invoices"]]
    assert numbers == sorted(numbers, reverse=True)


def test_dashboard_fully_paid_bill_not_counted_as_outstanding(client, sample_item):
    client.post(
        "/api/bills",
        json={
            "customer_name": "Bob", "customer_type": "retailer",
            "items": [{"item_id": sample_item.id, "quantity": 1, "unit_price": 100.0}],
        },
        headers=AUTH_HEADERS,
    )
    data = client.get("/api/dashboard", headers=AUTH_HEADERS).json()
    assert data["today"]["outstanding_amount"] == 0
    assert data["sales"]["pending_payment_count"] == 0
