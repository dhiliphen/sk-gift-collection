from sqlalchemy.orm import Session, joinedload
from app import models
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.PurchaseOrder, db)

    def get_all_ordered(self) -> list[models.PurchaseOrder]:
        return (
            self.db.query(models.PurchaseOrder)
            .options(joinedload(models.PurchaseOrder.items))
            .order_by(models.PurchaseOrder.id.desc())
            .all()
        )

    def get_with_items(self, order_id: int):
        return (
            self.db.query(models.PurchaseOrder)
            .options(joinedload(models.PurchaseOrder.items))
            .filter(models.PurchaseOrder.id == order_id)
            .first()
        )

    def add_item(self, item: models.PurchaseOrderItem):
        self.db.add(item)
