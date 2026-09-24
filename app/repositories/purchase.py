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
