from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class PaymentRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Payment, db)

    def get_by_bill(self, bill_id: int) -> list[models.Payment]:
        return (
            self.db.query(models.Payment)
            .filter(models.Payment.bill_id == bill_id)
            .order_by(models.Payment.id.asc())
            .all()
        )

    def sum_received_today(self):
        """Total of payments actually recorded today (UTC date), excluding
        voided/cancelled payment entries."""
        today = datetime.utcnow().date().isoformat()
        return (
            self.db.query(func.coalesce(func.sum(models.Payment.amount), 0))
            .filter(
                func.date(models.Payment.payment_date) == today,
                models.Payment.status == "recorded",
            )
            .scalar()
        )

    def get_weekly_received_trend(self) -> list[dict]:
        """Daily total of payments actually recorded for the last 7 days
        (today inclusive, oldest first), excluding voided entries. Days
        with no payments report 0."""
        today = datetime.utcnow().date()
        start = today - timedelta(days=6)
        rows = (
            self.db.query(
                func.date(models.Payment.payment_date).label("day"),
                func.coalesce(func.sum(models.Payment.amount), 0).label("received_amount"),
            )
            .filter(
                models.Payment.status == "recorded",
                func.date(models.Payment.payment_date) >= start.isoformat(),
            )
            .group_by("day")
            .all()
        )
        by_day = {r.day: r.received_amount for r in rows}
        return [
            {
                "date": (start + timedelta(days=i)).isoformat(),
                "received_amount": by_day.get((start + timedelta(days=i)).isoformat(), 0),
            }
            for i in range(7)
        ]
