from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Customer, db)

    def get_all_filtered(self, customer_type: Optional[str] = None) -> list[models.Customer]:
        q = self.db.query(models.Customer)
        if customer_type:
            q = q.filter(models.Customer.customer_type == customer_type)
        return q.order_by(models.Customer.name).all()
