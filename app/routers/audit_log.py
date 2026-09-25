from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import require_role
from app.repositories.audit import AuditRepository
from app.services.audit import AuditService

router = APIRouter(prefix="/api", tags=["audit"])


def get_service(db: Session = Depends(get_db)) -> AuditService:
    return AuditService(AuditRepository(db))


@router.get(
    "/audit-log",
    response_model=list[schemas.AuditLogResponse],
    dependencies=[Depends(require_role("ADMIN"))],
)
def get_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    service: AuditService = Depends(get_service),
):
    return service.get_recent(limit=limit, action=action)
