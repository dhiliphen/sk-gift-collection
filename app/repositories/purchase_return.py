from sqlalchemy.orm import Session, joinedload
from app import models
from app.repositories.base import BaseRepository


class PurchaseReturnRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.PurchaseReturn, db)

    def get_by_purchase(self, purchase_id: int) -> list[models.PurchaseReturn]:
        return (
            self.db.query(models.PurchaseReturn)
            .options(joinedload(models.PurchaseReturn.items))
            .filter(models.PurchaseReturn.purchase_id == purchase_id)
            .order_by(models.PurchaseReturn.id.desc())
            .all()
        )

    def get_with_items(self, return_id: int):
        return (
            self.db.query(models.PurchaseReturn)
            .options(joinedload(models.PurchaseReturn.items))
            .filter(models.PurchaseReturn.id == return_id)
            .first()
        )

    def add_item(self, item: models.PurchaseReturnItem):
        self.db.add(item)
