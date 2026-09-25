from typing import Optional
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.AuditLog, db)

    def get_recent(self, limit: int = 100, action: Optional[str] = None) -> list[models.AuditLog]:
        q = self.db.query(models.AuditLog)
        if action:
            q = q.filter(models.AuditLog.action == action)
        return q.order_by(models.AuditLog.id.desc()).limit(limit).all()
