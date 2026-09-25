import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import engine, SessionLocal
from app.models import Base, User
from app.routers import inventory, suppliers, categories, units, billing, customers, purchases, dashboard
from app.routers import auth as auth_router, users, audit_log
from app.auth import is_valid_session
from app.security import hash_password
from sqlalchemy import text, inspect as sa_inspect

Base.metadata.create_all(bind=engine)

# Migrate existing tables with new columns
def _add_col(conn, table, col, col_def):
    existing = [c['name'] for c in sa_inspect(engine).get_columns(table)]
    if col not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))

with engine.connect() as conn:
    _add_col(conn, 'inventory',   'wholesale_price',  'REAL DEFAULT 0.0')
    _add_col(conn, 'inventory',   'dealer_price',     'REAL DEFAULT 0.0')
    _add_col(conn, 'inventory',   'hsn_code',         'VARCHAR(20)')
    _add_col(conn, 'inventory',   'gst_rate',         'REAL DEFAULT 0.0')
    _add_col(conn, 'bills',       'customer_type',    "VARCHAR(20) DEFAULT 'retailer'")
    _add_col(conn, 'bills',       'taxable_amount',   'REAL DEFAULT 0.0')
    _add_col(conn, 'bills',       'igst_amount',      'REAL DEFAULT 0.0')
    _add_col(conn, 'bill_items',  'hsn_code',         'VARCHAR(20)')
    _add_col(conn, 'bill_items',  'unit',             'VARCHAR(20)')
    _add_col(conn, 'bill_items',  'gst_rate',         'REAL DEFAULT 0.0')
    _add_col(conn, 'purchase_bill_items', 'unit',     'VARCHAR(20)')
    _add_col(conn, 'bill_items',  'taxable_amount',   'REAL DEFAULT 0.0')
    _add_col(conn, 'bill_items',  'igst_amount',      'REAL DEFAULT 0.0')

    # Payment tracking: bills created before this migration were always paid
    # in full at creation time (the app's original cash-sale assumption), so
    # backfill them as fully paid rather than defaulting to unpaid.
    _bills_predate_payments = 'payment_state' not in [c['name'] for c in sa_inspect(engine).get_columns('bills')]
    _add_col(conn, 'bills', 'amount_paid',   'REAL DEFAULT 0.0')
    _add_col(conn, 'bills', 'payment_state', "VARCHAR(20) DEFAULT 'paid'")
    _add_col(conn, 'bills', 'due_date',      'DATETIME')
    if _bills_predate_payments:
        conn.execute(text("UPDATE bills SET amount_paid = total_amount, payment_state = 'paid'"))
    conn.commit()

# Seed a default admin account if none exists yet, so the app is usable
# immediately after a fresh deploy. Preserves the previous hardcoded
# credentials (admin/skgifts) by default for continuity with the old
# single-password login — set DEFAULT_ADMIN_PASSWORD to seed a different
# one instead, or change it from Settings > Users once logged in.
_db = SessionLocal()
try:
    if _db.query(User).count() == 0:
        _db.add(User(
            username="admin",
            password_hash=hash_password(os.environ.get("DEFAULT_ADMIN_PASSWORD", "skgifts")),
            role="ADMIN",
        ))
        _db.commit()
finally:
    _db.close()

_base = os.environ.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__)))

_PUBLIC_PATHS = ("/login", "/static", "/favicon.ico")
_INTERNAL_KEY = os.environ.get("INTERNAL_API_KEY", "")

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in _PUBLIC_PATHS):
            return await call_next(request)
        # Allow internal service calls via API key
        if _INTERNAL_KEY and request.url.path.startswith("/api/"):
            if request.headers.get("X-Internal-Key") == _INTERNAL_KEY:
                return await call_next(request)
        token = request.cookies.get("session")
        if not is_valid_session(token or ""):
            return RedirectResponse(url="/login")
        return await call_next(request)

app = FastAPI(title="Inventory Management API", version="1.0.0")
app.add_middleware(AuthMiddleware)
_static_dir = os.path.join(_base, "app", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
templates = Jinja2Templates(directory=os.path.join(_base, "app", "templates"))

app.include_router(auth_router.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(categories.router)
app.include_router(units.router)
app.include_router(billing.router)
app.include_router(customers.router)
app.include_router(purchases.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(audit_log.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
