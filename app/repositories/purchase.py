from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app import models
from app.repositories.base import BaseRepository


class PurchaseRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.PurchaseBill, db)

    def get_all_ordered(self) -> list[models.PurchaseBill]:
        return (
            self.db.query(models.PurchaseBill)
            .options(joinedload(models.PurchaseBill.items))
            .order_by(models.PurchaseBill.id.desc())
            .all()
        )

    def get_with_items(self, purchase_id: int):
        return (
            self.db.query(models.PurchaseBill)
            .options(joinedload(models.PurchaseBill.items))
            .filter(models.PurchaseBill.id == purchase_id)
            .first()
        )

    def add_item(self, item: models.PurchaseBillItem):
        self.db.add(item)

    def get_recent(self, limit: int = 5) -> list[models.PurchaseBill]:
        return (
            self.db.query(models.PurchaseBill)
            .options(joinedload(models.PurchaseBill.items))
            .order_by(models.PurchaseBill.id.desc())
            .limit(limit)
            .all()
        )

    def get_today_stats(self) -> dict:
        """Purchase total for goods received today (UTC date), excluding
        cancelled purchases."""
        today = datetime.utcnow().date().isoformat()
        row = (
            self.db.query(
                func.coalesce(func.sum(models.PurchaseBill.total_amount), 0).label("purchases_amount"),
            )
            .filter(
                func.date(models.PurchaseBill.created_at) == today,
                models.PurchaseBill.status != "cancelled",
            )
            .one()
        )
        return {"purchases_amount": row.purchases_amount}
