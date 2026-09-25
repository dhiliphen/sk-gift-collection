"""
One-time migration: backfill a Payment record for every existing bill that
was already marked fully paid (the app's original cash-sale assumption)
before payment tracking existed, so the payments ledger reconciles with
Bill.amount_paid. Safe to re-run: bills that already have a payment are
skipped.

Run with: python migrate_bill_payments.py
"""
from app.database import SessionLocal
from app import models


def migrate():
    db = SessionLocal()
    try:
        bills = db.query(models.Bill).filter(models.Bill.amount_paid > 0).all()
        has_payment = {
            row.bill_id
            for row in db.query(models.Payment.bill_id).distinct().all()
        }

        created = []
        skipped = []

        for bill in bills:
            if bill.id in has_payment:
                skipped.append(bill.invoice_number)
                continue
            db.add(models.Payment(
                bill_id=bill.id,
                amount=bill.amount_paid,
                payment_method="cash",
                notes="Backfilled at payment-tracking introduction — historical sale recorded as paid in full",
            ))
            created.append(bill.invoice_number)

        db.commit()

        print(f"Created : {len(created)}")
        for n in created:
            print(f"  + {n}")

        print(f"Skipped (already had payment history) : {len(skipped)}")
        for n in skipped:
            print(f"  = {n}")

    finally:
        db.close()


if __name__ == "__main__":
    migrate()
