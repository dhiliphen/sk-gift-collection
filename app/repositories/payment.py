from datetime import datetime
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
