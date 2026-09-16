import hashlib
import secrets

_USERNAME = "admin"
_PASSWORD_HASH = hashlib.sha256("skgifts".encode()).hexdigest()

# In-memory session store (cleared on server restart)
_sessions: set = set()


def verify_credentials(username: str, password: str) -> bool:
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    return username == _USERNAME and pw_hash == _PASSWORD_HASH


def create_session() -> str:
    token = secrets.token_hex(32)
    _sessions.add(token)
    return token


def is_valid_session(token: str) -> bool:
    return token in _sessions


def delete_session(token: str):
    _sessions.discard(token)
