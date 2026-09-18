"""
One-time migration: populate suppliers table from supplier names in items table.
Run with: python migrate_suppliers.py
"""
from app.database import SessionLocal
from app import models


def migrate():
    db = SessionLocal()
    try:
        # All unique non-null supplier names from items
        item_suppliers = (
            db.query(models.Item.supplier)
            .filter(models.Item.supplier.isnot(None), models.Item.supplier != "")
            .distinct()
            .all()
        )
        names = [row.supplier.strip() for row in item_suppliers if row.supplier.strip()]

        # Existing supplier names (lowercase for comparison)
        existing = {
            s.name.lower()
            for s in db.query(models.Supplier.name).all()
        }

        created = []
        skipped = []

        for name in names:
            if name.lower() in existing:
                skipped.append(name)
            else:
                db.add(models.Supplier(name=name))
                existing.add(name.lower())
                created.append(name)

        db.commit()

        print(f"Created : {len(created)}")
        for n in created:
            print(f"  + {n}")

        print(f"Skipped : {len(skipped)}")
        for n in skipped:
            print(f"  = {n}")

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
