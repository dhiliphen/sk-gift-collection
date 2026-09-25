from sqlalchemy.orm import Session, joinedload
from app import models
from app.repositories.base import BaseRepository


class SalesReturnRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.SalesReturn, db)

    def get_by_bill(self, bill_id: int) -> list[models.SalesReturn]:
        return (
            self.db.query(models.SalesReturn)
            .options(joinedload(models.SalesReturn.items))
            .filter(models.SalesReturn.bill_id == bill_id)
            .order_by(models.SalesReturn.id.desc())
            .all()
        )

    def get_with_items(self, return_id: int):
        return (
            self.db.query(models.SalesReturn)
            .options(joinedload(models.SalesReturn.items))
            .filter(models.SalesReturn.id == return_id)
            .first()
        )

    def add_item(self, item: models.SalesReturnItem):
        self.db.add(item)
