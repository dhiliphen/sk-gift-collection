from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Category, db)

    def get_all_ordered(self) -> list[models.Category]:
        return self.db.query(models.Category).order_by(models.Category.name).all()

    def get_by_name(self, name: str) -> Optional[models.Category]:
        return self.db.query(models.Category).filter(models.Category.name == name).first()
