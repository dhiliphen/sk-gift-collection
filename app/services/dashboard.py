from app.repositories.bill import BillRepository
from app.repositories.purchase import PurchaseRepository
from app.repositories.item import ItemRepository
from app.repositories.payment import PaymentRepository


class DashboardService:
    """Aggregates business data from across inventory, sales, and purchases
    into a single read model for the dashboard: numbers, short
    recent-activity lists, a 7-day sales/receipts trend, and an
    invoice-status breakdown for the dashboard's charts."""

    def __init__(
        self,
        bill_repo: BillRepository,
        purchase_repo: PurchaseRepository,
        item_repo: ItemRepository,
        payment_repo: PaymentRepository,
    ):
        self.bill_repo = bill_repo
        self.purchase_repo = purchase_repo
        self.item_repo = item_repo
        self.payment_repo = payment_repo

    def get_dashboard(self) -> dict:
        today_sales = self.bill_repo.get_today_stats()
        today_purchases = self.purchase_repo.get_today_stats()
        payments_received_today = self.payment_repo.sum_received_today()
        outstanding_amount = self.bill_repo.sum_outstanding()

        item_stats = self.item_repo.get_stats()
        overdue_count = self.bill_repo.count_overdue()
        pending_payment_count = self.bill_repo.count_pending_payment()

        sales_trend = self.bill_repo.get_weekly_sales_trend()
        received_trend = self.payment_repo.get_weekly_received_trend()
        received_by_date = {r["date"]: r["received_amount"] for r in received_trend}
        trend = [
            {
                "date": s["date"],
                "sales_amount": s["sales_amount"],
                "received_amount": received_by_date.get(s["date"], 0),
            }
            for s in sales_trend
        ]
        payment_breakdown = self.bill_repo.get_payment_breakdown()

        alerts = []
        if item_stats["low_stock_count"] > 0:
            alerts.append({
                "level": "warning",
                "message": f"{item_stats['low_stock_count']} product(s) are below minimum stock",
            })
        if item_stats["out_of_stock_count"] > 0:
            alerts.append({
                "level": "warning",
                "message": f"{item_stats['out_of_stock_count']} product(s) are out of stock",
            })
        if overdue_count > 0:
            alerts.append({
                "level": "warning",
                "message": f"{overdue_count} customer invoice(s) are overdue",
            })
        if today_sales["invoice_count"] > 0:
            alerts.append({
                "level": "info",
                "message": f"{today_sales['invoice_count']} invoice(s) created today",
            })

        return {
            "today": {
                "sales_amount": today_sales["sales_amount"],
                "purchases_amount": today_purchases["purchases_amount"],
                "payments_received": payments_received_today,
                "outstanding_amount": outstanding_amount,
            },
            "inventory": {
                "total_products": item_stats["total_items"],
                "stock_value": item_stats["total_value"],
                "low_stock_count": item_stats["low_stock_count"],
                "out_of_stock_count": item_stats["out_of_stock_count"],
            },
            "sales": {
                "invoices_today": today_sales["invoice_count"],
                "pending_payment_count": pending_payment_count,
                "recent_invoices": self.bill_repo.get_recent(5),
            },
            "purchases": {
                "recent_purchases": self.purchase_repo.get_recent(5),
            },
            "alerts": alerts,
            "trend": trend,
            "payment_breakdown": payment_breakdown,
        }
