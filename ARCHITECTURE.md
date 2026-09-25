# Architecture

SK Gift Collection is a FastAPI + SQLAlchemy (SQLite) + Jinja2 business system: inventory, sales, purchasing, payments, GST, and audit/RBAC for a small retail/wholesale gift shop. This document describes the current architecture. For what the business rules actually are (and which ones were deliberately left as open questions rather than invented), see `BUSINESS_RULES.md`. For test coverage and known risks, see `QA_REPORT.md`.

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI 0.111 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (file-based; `./inventory.db` locally, a Railway volume in production) |
| Templates | Jinja2 (server-rendered login page + print views; the main app is a single-page app) |
| Frontend | Plain HTML/CSS/JS — no framework, no build step, no bundler |
| Auth | Session cookie (server-side in-memory store) + an `X-Internal-Key` header for service-to-service calls |
| Packaging | `pip` + `requirements.txt`; also ships as a Windows desktop EXE via PyInstaller (`launcher.py`, `inventory.spec`) |
| Deployment | Railway (`Procfile`), auto-deploys on push to `main` |

No ORM migration tool (Alembic, etc.) is used. Schema evolution is handled by `main.py` at startup: `Base.metadata.create_all()` creates any tables that don't exist yet, and a small `_add_col()` helper runs idempotent `ALTER TABLE ... ADD COLUMN` statements for columns added to existing tables. This has been sufficient for a single-table-owner SQLite app with one deployment target; it would not scale to a team needing reviewable migration diffs or multi-environment schema drift detection.

## Layering

```
UI (app/templates/index.html — vanilla JS, fetch() against the REST API)
  |
API routers (app/routers/*.py — request validation, response shaping, audit logging)
  |
Services (app/services/*.py — business rules, transactions, orchestration)
  |
Repositories (app/repositories/*.py — SQLAlchemy queries, no business logic)
  |
Database (SQLite)
```

Each domain (items, bills, purchases, purchase orders, sales/purchase returns, payments, customers, suppliers, categories, units, users, audit log, dashboard) follows the same triad: a repository for data access, a service for business rules and transaction boundaries, and a router that wires HTTP in and out. Routers depend on services via FastAPI's `Depends()`; services depend on repositories the same way. This keeps business rules in one place per domain and out of both the UI and the route handlers.

**Where this is intentionally bent:** audit logging (`app/audit.py`) is called from routers, not services. "Who made this HTTP request" is a web-request concern, not something a domain service should need to know about — threading a `current_user` parameter through every service method across eight domains for a cross-cutting concern would have coupled the domain layer to the web layer for no benefit. The trade-off: a service called directly (from a script, a future background job, etc.) will not produce an audit entry. That's acceptable today because every mutation currently happens through the API.

## Directory layout

```
inventory_app/
├── main.py                    FastAPI app construction, startup migrations, admin seeding
├── launcher.py                PyInstaller entry point (desktop build)
├── inventory.spec             PyInstaller build spec
├── load_sample_data.py        Dev convenience: populate sample inventory
├── migrate_suppliers.py       One-time: backfill suppliers table from item.supplier strings
├── migrate_stock_ledger.py    One-time: backfill StockMovement rows for pre-ledger items
├── migrate_bill_payments.py   One-time: backfill Payment rows for pre-payment-tracking bills
├── app/
│   ├── database.py            Engine, SessionLocal, get_db dependency
│   ├── models.py               All SQLAlchemy ORM models
│   ├── schemas.py               All Pydantic request/response models
│   ├── money.py                 Decimal `Money` type used for every currency/rate field
│   ├── auth.py                   Session store, credential check, get_current_user, require_role
│   ├── security.py               Password hashing (PBKDF2-HMAC-SHA256, stdlib only)
│   ├── audit.py                  record() — the one function that writes an AuditLog row
│   ├── utils.py                  amount_in_words (Indian numbering)
│   ├── repositories/              One file per domain; BaseRepository has generic CRUD
│   ├── services/                  One file per domain; tax.py is the shared GST engine
│   ├── routers/                   One file per domain, mounted under /api in main.py
│   ├── static/                    (if present) served at /static
│   └── templates/
│       ├── index.html            The entire application UI (single file, ~4,800 lines)
│       ├── login.html
│       ├── print_invoice.html    Tally-Prime-style GST invoice print view
│       └── print_purchase.html
└── tests/                      pytest suite, one file per domain + conftest.py fixtures
```

## Domain modules

| Domain | Repository | Service | Router | Notes |
|---|---|---|---|---|
| Inventory | `item.py` | `item.py` | `inventory.py` | Also owns the stock ledger (`apply_stock_change`) |
| Sales invoices | `bill.py` | `bill.py` | `billing.py` | Also owns payments and sales returns endpoints (nested) |
| Payments | `payment.py` | (methods on `BillService`) | (endpoints on `billing.py`) | Not a separate service — a bill's payment lifecycle is small enough to live with it |
| Sales returns | `sales_return.py` | `sales_return.py` | (endpoints on `billing.py`) | Credit notes; nested under `/api/bills/{id}/returns` |
| Purchases (goods receipt) | `purchase.py` | `purchase.py` | `purchases.py` | This is the original "simple flow" purchase; also owns purchase returns |
| Purchase orders | `purchase_order.py` | `purchase_order.py` | `purchase_orders.py` | Pre-receipt commitment; never touches stock |
| Purchase returns | `purchase_return.py` | `purchase_return.py` | (endpoints on `purchases.py`) | Debit notes; nested under `/api/purchases/{id}/returns` |
| Customers | `customer.py` | `customer.py` | `customers.py` | |
| Suppliers | `supplier.py` | `supplier.py` | `suppliers.py` | |
| Categories / Units | `category.py`, `unit.py` | same | `categories.py`, `units.py` | Simple lookup CRUD |
| Users / RBAC | `user.py` | `user.py` | `users.py` | Also `GET /api/users/me` for frontend role-awareness |
| Audit log | `audit.py` | `audit.py` | `audit_log.py` | Read-only; admin-gated |
| Dashboard | (composes bill/purchase/item/payment repos) | `dashboard.py` | `dashboard.py` | Aggregation only, no new tables |
| Auth | — | `app/auth.py` (session/credential logic) | `auth.py` (login/logout routes) | |

## Data model

Key entities and how they relate:

```
Customer ⟵ (name snapshot, not FK) ⟶ Bill ⟶ BillItem ⟶ (item_id snapshot)
                                       │              │
                                       ├─ Payment      └─ quantity_returned (tracks SalesReturn)
                                       └─ SalesReturn ⟶ SalesReturnItem

Supplier ⟵ (name snapshot) ⟶ PurchaseOrder ⟶ PurchaseOrderItem (quantity_received)
                                    │
                                    └─(optional)─ PurchaseBill ⟶ PurchaseBillItem
                                                        │              │
                                                        │              └─ quantity_returned
                                                        └─ PurchaseReturn ⟶ PurchaseReturnItem

Item ⟶ StockMovement (append-only ledger; every stock change of any kind)

User ⟶ (session token, in-memory) ⟶ AuditLog (username snapshot, not FK)
```

Design principles that show up repeatedly:

- **Snapshot, don't reference, for anything printed or historical.** `BillItem` stores `item_name`, `unit_price`, `gst_rate` at the time of sale, not a live join to `Item` — so an invoice still reads correctly after the item's price changes or the item is deleted. The same applies to `customer_name` on `Bill`, `supplier_name` on `PurchaseBill`/`PurchaseOrder`, and `username` on `AuditLog`.
- **The ledger is the source of truth; the running total is a cache.** `Item.quantity` is fast to read but `StockMovement` is what you'd reconcile against. Every code path that changes stock goes through `ItemRepository.apply_stock_change()`, which writes both in one place.
- **Cancel, don't delete.** Every transactional document (`Bill`, `PurchaseBill`, `PurchaseOrder`, `Payment`, `SalesReturn`, `PurchaseReturn`) has a status field with a cancelled/voided state instead of a delete endpoint. History stays queryable.
- **Original documents are immutable once side effects exist.** A `Payment` changes `Bill.amount_paid`; a `SalesReturn`/`PurchaseReturn` changes stock. Neither ever rewrites the parent `Bill`/`PurchaseBill`'s own total or line items after the fact.

## Money

Every currency and tax-rate field uses `app.money.Money` — a Pydantic-side `Decimal` with two properties:

1. Input (float, int, or string) is parsed through `Decimal(str(value))`, never `Decimal(float)`, so `2.675` doesn't pick up binary floating-point noise before it's even validated.
2. It's quantized to 2 decimal places immediately on validation.

That second point is not just a business-precision choice — it's a fix for a real bug found during this project: SQLite has no native `Decimal` type, so a `Numeric` column's value still round-trips through a float at the SQLite layer, and SQLAlchemy's sqlite dialect re-derives the Decimal on *read* via Python's `round(float_value, scale)`. Without quantizing on the way in, a raw `2.675` would silently come back as `2.67` on the next read — reintroducing the exact class of bug `Decimal` is supposed to prevent. **Any new monetary field must use the `Money` type, not a bare `Decimal` or `float`.**

Database columns use `app.models.MONEY` (`Numeric(12, 2)`). GST calculation is centralized in `app/services/tax.py` — `calculate_line_tax()` for line-level taxable/tax/total, `split_cgst_sgst()` for the printed invoice's tax breakup — so no router or template computes GST independently.

## Auth and RBAC

- `User` (username, PBKDF2-hashed password, role, is_active) replaced a hardcoded constant. A default `admin` user is seeded automatically on first startup (see `BUSINESS_RULES.md` for the exact credential-continuity guarantee).
- Sessions are an in-memory `dict[token, user_id]` (`app.auth._sessions`) — simple, but cleared on every process restart, and does not work across multiple server instances. Acceptable for a single-instance Railway deployment; would need a shared store (Redis, a DB table) to scale out.
- `require_role(*roles)` is a FastAPI dependency factory. It is used in exactly one place today — the audit log endpoint — deliberately. See `BUSINESS_RULES.md` for why RBAC enforcement was kept minimal rather than retrofitted everywhere.
- `X-Internal-Key` bypasses session auth entirely for trusted service-to-service calls (and is how the test suite authenticates). `require_role` treats an internal-key request as trusted and skips the role check, since there's no human user to check a role against.

## Audit trail

`app/audit.py::record()` writes one `AuditLog` row per call: `username`, `action`, `entity_type`, `entity_id`, `old_value`/`new_value` (JSON). It is called from routers immediately after a mutation has already committed successfully — it is a best-effort secondary write, not part of the same transaction as the business mutation. `old_value`/`new_value` are built from the same Pydantic response schemas the API already returns, which has one deliberate side effect: since no schema for `User` ever includes `password_hash`, a login/user-management event can't leak a credential into the audit trail even by accident.

## Frontend

`app/templates/index.html` is the entire application UI — one file, plain JavaScript, no build step. Views are `<div id="view-X">` blocks toggled by `switchView()`; each view has its own `load*()` function registered in a `loaders` map. Modals follow one consistent pattern (`.modal-overlay` / `.modal`, opened by adding an `active` class, closed via `closeModal(id)`). Three themes (Sandal/White/Dark) are CSS custom properties swapped via `data-theme` on `<html>`.

This does not scale indefinitely — at ~4,800 lines it is already large for a single file — but splitting it was out of scope for this project's feature work, and every phase so far has been additive to the same file successfully.

## Deployment

- **Railway**: `Procfile` runs `uvicorn main:app --host 0.0.0.0 --port $PORT`. Python is pinned to 3.11 via `.python-version` (Railway's default 3.13 breaks SQLAlchemy 2.0.30's greenlet dependency). The SQLite file lives on a mounted Railway volume; `DB_PATH` env var controls its location.
- **Desktop (Windows EXE)**: `launcher.py` is the PyInstaller entry point — it stores the DB under `~/SKGiftCollection/inventory.db` and opens a browser window on startup. CI builds this automatically on push to `main` (`.github/workflows/build.yml`).
- **One-time migration scripts** (`migrate_suppliers.py`, `migrate_stock_ledger.py`, `migrate_bill_payments.py`) exist for backfilling historical data when a new feature introduces a table that needs seeding from pre-existing rows. They are not run automatically — a human runs them once per environment. As of this writing they have been run against the local dev database; the current owner has explicitly chosen *not* to backfill history against the Railway production database for the stock ledger and payment history (letting those start fresh from their respective deploy dates) — see `BUSINESS_RULES.md`.
