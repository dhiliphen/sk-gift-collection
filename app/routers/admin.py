from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from app.auth import require_role
from app.database import _db_path

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/export-db", dependencies=[Depends(require_role("ADMIN"))])
def export_db():
    """Download the raw SQLite database file — a manual backup/export,
    ADMIN-only. Mainly useful right now for pulling production data down
    to a local machine (e.g. ahead of a Postgres/MySQL migration)."""
    return FileResponse(
        _db_path,
        media_type="application/octet-stream",
        filename="inventory_export.db",
    )
