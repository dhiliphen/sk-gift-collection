"""
One-time migration: backfill an OPENING_STOCK movement for every existing
item so the stock_movements ledger reconciles with current on-hand quantity
from this point forward. Safe to re-run: items that already have a movement
are skipped.

Run with: python migrate_stock_ledger.py
"""
from app.database import SessionLocal
from app import models


def migrate():
    db = SessionLocal()
    try:
        items = db.query(models.Item).all()
        has_movement = {
            row.item_id
            for row in db.query(models.StockMovement.item_id).distinct().all()
        }

        created = []
        skipped = []

        for item in items:
            if item.id in has_movement:
                skipped.append(item.name)
                continue
            db.add(models.StockMovement(
                item_id=item.id,
                movement_type="OPENING_STOCK",
                quantity_change=item.quantity,
                quantity_before=0,
                quantity_after=item.quantity,
                reference_type="item_create",
                reference_id=item.id,
                note="Backfilled at stock-ledger introduction",
            ))
            created.append(item.name)

        db.commit()

        print(f"Created : {len(created)}")
        for n in created:
            print(f"  + {n}")

        print(f"Skipped (already had ledger history) : {len(skipped)}")
        for n in skipped:
            print(f"  = {n}")

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
