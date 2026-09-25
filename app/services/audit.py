from typing import Optional
from app import models
from app.repositories.audit import AuditRepository


class AuditService:
    def __init__(self, repo: AuditRepository):
        self.repo = repo

    def get_recent(self, limit: int = 100, action: Optional[str] = None) -> list[models.AuditLog]:
        return self.repo.get_recent(limit=limit, action=action)
