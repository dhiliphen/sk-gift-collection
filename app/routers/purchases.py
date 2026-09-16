from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


@router.get("", response_model=list[schemas.PurchaseResponse])
def get_all_purchases(db: Session = Depends(get_db)):
    return db.query(models.PurchaseBill).order_by(models.PurchaseBill.id.desc()).all()


@router.get("/{purchase_id}", response_model=schemas.PurchaseResponse)
def get_purchase(purchase_id: int, db: Session = Depends(get_db)):
    pb = db.query(models.PurchaseBill).filter(models.PurchaseBill.id == purchase_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    return pb


@router.post("", response_model=schemas.PurchaseResponse, status_code=201)
def create_purchase(purchase: schemas.PurchaseCreate, db: Session = Depends(get_db)):
    if not purchase.items:
        raise HTTPException(status_code=400, detail="Purchase must have at least one item")

    # Resolve items
    resolved = []
    for line in purchase.items:
        item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
        resolved.append((item, line))

    # Create purchase bill
    db_bill = models.PurchaseBill(
        purchase_number="TMP",
        supplier_name=purchase.supplier_name,
        supplier_invoice=purchase.supplier_invoice,
        status="received",
        total_amount=0.0,
    )
    db.add(db_bill)
    db.flush()

    db_bill.purchase_number = f"PUR-{db_bill.id:04d}"

    total = 0.0
    for item, line in resolved:
        line_total = round(line.quantity * line.unit_cost, 2)
        total += line_total
        # Add stock
        item.quantity += line.quantity
        db.add(models.PurchaseBillItem(
            bill_id=db_bill.id,
            item_id=item.id,
            item_name=item.name,
            quantity=line.quantity,
            unit_cost=line.unit_cost,
            line_total=line_total,
        ))

    db_bill.total_amount = round(total, 2)
    db.commit()
    db.refresh(db_bill)
    return db_bill


@router.patch("/{purchase_id}/cancel", response_model=schemas.PurchaseResponse)
def cancel_purchase(purchase_id: int, db: Session = Depends(get_db)):
    pb = db.query(models.PurchaseBill).filter(models.PurchaseBill.id == purchase_id).first()
    if not pb:
        raise HTTPException(status_code=404, detail="Purchase bill not found")
    if pb.status == "cancelled":
        raise HTTPException(status_code=400, detail="Already cancelled")

    # Deduct stock back
    for line in pb.items:
        if line.item_id:
            item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
            if item:
                item.quantity = max(0, item.quantity - line.quantity)

    pb.status = "cancelled"
    db.commit()
    db.refresh(pb)
    return pb
