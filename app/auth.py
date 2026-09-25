import secrets
from typing import Optional
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.security import verify_password

# In-memory session store (cleared on server restart): token -> user_id.
_sessions: dict[str, int] = {}


def verify_credentials(db: Session, username: str, password: str) -> Optional[models.User]:
    user = (
        db.query(models.User)
        .filter(models.User.username == username, models.User.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = user_id
    return token


def is_valid_session(token: str) -> bool:
    return token in _sessions


def delete_session(token: str):
    _sessions.pop(token, None)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[models.User]:
    """The logged-in User for a session-cookie request, or None for an
    internal-service (X-Internal-Key) request — there's no human user to
    attribute those to."""
    token = request.cookies.get("session")
    user_id = _sessions.get(token) if token else None
    if user_id is None:
        return None
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_current_username(request: Request, db: Session = Depends(get_db)) -> str:
    user = get_current_user(request, db)
    return user.username if user else "system"


def require_role(*roles: str):
    """FastAPI dependency factory: restricts a route to the given roles.
    Internal (X-Internal-Key) requests have no user and are treated as
    trusted system calls, bypassing the check — the auth middleware has
    already authenticated them as a trusted internal service, not an
    unprivileged human, before this dependency ever runs."""
    def checker(request: Request, db: Session = Depends(get_db)):
        user = get_current_user(request, db)
        if user is not None and user.role not in roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this")
    return checker
