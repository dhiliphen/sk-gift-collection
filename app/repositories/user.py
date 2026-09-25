from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.User, db)

    def get_by_username(self, username: str) -> Optional[models.User]:
        return self.db.query(models.User).filter(models.User.username == username).first()

    def get_all_ordered(self) -> list[models.User]:
        return self.db.query(models.User).order_by(models.User.id.asc()).all()
