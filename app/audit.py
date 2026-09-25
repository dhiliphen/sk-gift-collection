"""
Thin audit-trail recorder, called from routers right after a mutation has
already succeeded and committed. Deliberately kept out of the service
layer: "who is making this HTTP request" is a web-request concern, not a
domain concept the business services should need to know about.

This writes its own small commit rather than joining the caller's
transaction — by the time record() runs, the primary business operation
has already committed, so the audit entry is a best-effort secondary
write, not something that needs to be atomic with it.

NEVER pass a raw User/password snapshot here — old_value/new_value should
come from the same Pydantic response schemas the API already returns,
which never include password_hash.
"""
import json
from typing import Optional
from sqlalchemy.orm import Session
from app import models


def record(
    db: Session,
    username: str,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    old_value: Optional[dict] = None,
    new_value: Optional[dict] = None,
) -> None:
    db.add(models.AuditLog(
        username=username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=json.dumps(old_value, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, default=str) if new_value is not None else None,
    ))
    db.commit()
