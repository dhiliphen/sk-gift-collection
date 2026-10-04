from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app import models
from app.repositories.base import BaseRepository


class BillRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Bill, db)

    def get_all_ordered(self) -> list[models.Bill]:
        return (
            self.db.query(models.Bill)
            .options(joinedload(models.Bill.items))
            .order_by(models.Bill.id.desc())
            .all()
        )

    def get_with_items(self, bill_id: int):
        return (
            self.db.query(models.Bill)
            .options(joinedload(models.Bill.items))
            .filter(models.Bill.id == bill_id)
            .first()
        )

    def add_item(self, bill_item: models.BillItem):
        self.db.add(bill_item)

    def get_recent(self, limit: int = 5) -> list[models.Bill]:
        return (
            self.db.query(models.Bill)
            .options(joinedload(models.Bill.items))
            .order_by(models.Bill.id.desc())
            .limit(limit)
            .all()
        )

    def get_today_stats(self) -> dict:
        """Sales total and invoice count for bills created today (UTC date,
        matching how created_at's server-side CURRENT_TIMESTAMP is stored),
        excluding cancelled bills."""
        today = datetime.utcnow().date().isoformat()
        row = (
            self.db.query(
                func.coalesce(func.sum(models.Bill.total_amount), 0).label("sales_amount"),
                func.count(models.Bill.id).label("invoice_count"),
            )
            .filter(
                func.date(models.Bill.created_at) == today,
                models.Bill.status != "cancelled",
            )
            .one()
        )
        return {"sales_amount": row.sales_amount, "invoice_count": row.invoice_count}

    def sum_outstanding(self):
        """Total balance due across all active (non-cancelled) bills that
        aren't fully paid."""
        return (
            self.db.query(
                func.coalesce(func.sum(models.Bill.total_amount - models.Bill.amount_paid), 0)
            )
            .filter(models.Bill.status != "cancelled", models.Bill.payment_state != "paid")
            .scalar()
        )

    def count_pending_payment(self) -> int:
        """Active bills that are unpaid or partially paid (overdue included)."""
        return (
            self.db.query(func.count(models.Bill.id))
            .filter(models.Bill.status != "cancelled", models.Bill.payment_state != "paid")
            .scalar()
        ) or 0

    def count_overdue(self) -> int:
        """Mirrors Bill.payment_status's "overdue" derivation: an active,
        not-fully-paid bill whose optional due_date has passed."""
        now = datetime.utcnow()
        return (
            self.db.query(func.count(models.Bill.id))
            .filter(
                models.Bill.status != "cancelled",
                models.Bill.payment_state != "paid",
                models.Bill.due_date.isnot(None),
                models.Bill.due_date < now,
            )
            .scalar()
        ) or 0

    def get_weekly_sales_trend(self) -> list[dict]:
        """Daily sales total for the last 7 days (today inclusive, oldest
        first), excluding cancelled bills. Days with no bills report 0 —
        used to chart invoiced-vs-received on the dashboard."""
        today = datetime.utcnow().date()
        start = today - timedelta(days=6)
        rows = (
            self.db.query(
                func.date(models.Bill.created_at).label("day"),
                func.coalesce(func.sum(models.Bill.total_amount), 0).label("sales_amount"),
            )
            .filter(
                models.Bill.status != "cancelled",
                func.date(models.Bill.created_at) >= start.isoformat(),
            )
            .group_by("day")
            .all()
        )
        by_day = {r.day: r.sales_amount for r in rows}
        return [
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "sales_amount": by_day.get((start + timedelta(days=i)).isoformat(), 0),
            }
            for i in range(7)
        ]

    def get_payment_breakdown(self) -> dict:
        """Counts of all bills grouped by their derived payment_status
        (paid/partially_paid/unpaid/overdue/cancelled). Reuses the
        Bill.payment_status property rather than re-deriving the
        overdue/cancelled logic in SQL, so the two can't drift apart."""
        counts = {"paid": 0, "partially_paid": 0, "unpaid": 0, "overdue": 0, "cancelled": 0}
        for bill in self.db.query(models.Bill).all():
            counts[bill.payment_status] += 1
        return counts
