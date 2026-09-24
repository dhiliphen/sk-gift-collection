from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class UnitRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Unit, db)

    def get_all_ordered(self) -> list[models.Unit]:
        return self.db.query(models.Unit).order_by(models.Unit.name).all()

    def get_by_name(self, name: str) -> Optional[models.Unit]:
        return self.db.query(models.Unit).filter(models.Unit.name == name).first()
