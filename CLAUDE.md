# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run dev server with hot-reload
uvicorn main:app --reload

# Run standalone (opens browser automatically)
python launcher.py

# Populate DB with sample data
python load_sample_data.py

# Build Windows EXE (CI runs this automatically on push to main)
pip install pyinstaller && pyinstaller inventory.spec
```

- Web UI: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`

## Architecture

**Stack:** FastAPI + SQLAlchemy (SQLite) + Jinja2 + plain JS frontend (no build step)

**Entry points:**
- `main.py` — development/server use; registers all routers, creates DB tables, runs schema migrations, serves `app/templates/index.html` at `/`
- `launcher.py` — PyInstaller wrapper; stores DB in `~/SKGiftCollection/inventory.db` when bundled, opens browser on startup

**Router layout** (`app/routers/`): each file owns one domain — `inventory`, `billing`, `purchases`, `suppliers`, `customers`, `categories`, `units`. All mounted under `/api/` prefix.

**Database:** SQLite at `./inventory.db` by default; override with `DB_PATH` env var. `app/database.py` manages the SQLAlchemy session. Schema is auto-created on startup and extended via raw `ALTER TABLE` migrations in `main.py` for post-deploy column additions.

**Frontend:** Single-page `app/templates/index.html` (~122KB). Uses `fetch()` against the REST API. Supports three themes (Sandal/White/Dark). No framework, no build step.

**Domain concepts:**
- Items have multi-tier pricing: `cost_price`, `wholesale_price`, `dealer_price`, `selling_price`
- Bills (`INV-####`) and Purchases (`PUR-####`) are auto-numbered; cancellation reverses stock
- Customer type (wholesaler/dealer/retailer) determines which price tier is used
- GST/IGST/HSN fields support Indian tax compliance

## Key files

| File | Purpose |
|------|---------|
| `app/models.py` | All SQLAlchemy ORM models |
| `app/schemas.py` | Pydantic request/response schemas |
| `app/database.py` | DB engine, session, `get_db` dependency |
| `inventory.spec` | PyInstaller build spec |
| `.github/workflows/build.yml` | CI: builds Windows EXE on push to `main` |
