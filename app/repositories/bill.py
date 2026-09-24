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
