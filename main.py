import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import engine
from app.models import Base
from app.routers import inventory, suppliers, categories, units, billing, customers, purchases
from app.routers import auth as auth_router
from app.auth import is_valid_session
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
    _add_col(conn, 'bill_items',  'gst_rate',         'REAL DEFAULT 0.0')
    _add_col(conn, 'bill_items',  'taxable_amount',   'REAL DEFAULT 0.0')
    _add_col(conn, 'bill_items',  'igst_amount',      'REAL DEFAULT 0.0')
    conn.commit()

_base = os.environ.get('BASE_DIR', os.path.dirname(os.path.abspath(__file__)))

_PUBLIC_PATHS = ("/login", "/static", "/favicon.ico")

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if any(request.url.path.startswith(p) for p in _PUBLIC_PATHS):
            return await call_next(request)
        token = request.cookies.get("session")
        if not is_valid_session(token or ""):
            return RedirectResponse(url="/login")
        return await call_next(request)

app = FastAPI(title="Inventory Management API", version="1.0.0")
app.add_middleware(AuthMiddleware)
app.mount("/static", StaticFiles(directory=os.path.join(_base, "app", "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(_base, "app", "templates"))

app.include_router(auth_router.router)
app.include_router(inventory.router)
app.include_router(suppliers.router)
app.include_router(categories.router)
app.include_router(units.router)
app.include_router(billing.router)
app.include_router(customers.router)
app.include_router(purchases.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
