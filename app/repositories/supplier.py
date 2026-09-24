from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Supplier, db)

    def get_by_name(self, name: str) -> Optional[models.Supplier]:
        return self.db.query(models.Supplier).filter(models.Supplier.name == name).first()
