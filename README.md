# INVNTRY — Inventory Management App

A reusable FastAPI + SQLite inventory module with a clean web UI.

## Features
- Add new inventory items (name, category, supplier, price, quantity)
- Edit existing items
- Add / remove stock with a dedicated stock update flow
- Low stock alerts with visual flags
- Dashboard stats (total items, portfolio value, low stock count)
- Search & filter
- Auto-generated REST API docs at `/docs`

## Project Structure
```
inventory_app/
├── main.py              ← FastAPI app, all routes
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── database.py      ← SQLAlchemy engine + session
│   ├── models.py        ← Item DB model
│   ├── schemas.py       ← Pydantic request/response models
│   └── templates/
│       └── index.html   ← Web UI
```

## Setup & Run

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
uvicorn main:app --reload

# 4. Open in browser
# UI:   http://localhost:8000
# Docs: http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/items | List all items |
| GET | /api/items/{id} | Get single item |
| POST | /api/items | Create new item |
| PUT | /api/items/{id} | Update item details |
| PATCH | /api/items/{id}/stock | Add/remove stock |
| DELETE | /api/items/{id} | Delete item |
| GET | /api/stats | Dashboard stats |

## Reuse
This module is designed to be imported into any larger FastAPI project.
Register the routes as an APIRouter to embed inside another app.
