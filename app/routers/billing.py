import os
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas
from app.utils import amount_in_words

_base = os.environ.get('BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_templates = Jinja2Templates(directory=os.path.join(_base, "app", "templates"))

_COMPANY = {
    "name":    os.environ.get("COMPANY_NAME",    "SK Gift Collection"),
    "line2":   os.environ.get("COMPANY_LINE2",   "Dealers in Divam Agarbathi"),
    "address": os.environ.get("COMPANY_ADDRESS", "Shop No. 21, Behind Kamaraj School, Gandhi Nagar, Dharavi, Mumbai - 400017"),
    "state":   os.environ.get("COMPANY_STATE",   "Maharashtra"),
    "pin":     os.environ.get("COMPANY_PIN",     "400017"),
    "phone":   os.environ.get("COMPANY_PHONE",   "9820 76 9225"),
    "email":   os.environ.get("COMPANY_EMAIL",   ""),
    "gstin":   os.environ.get("COMPANY_GSTIN",   ""),
}

router = APIRouter(prefix="/api/bills", tags=["billing"])


@router.get("", response_model=list[schemas.BillResponse])
def get_all_bills(db: Session = Depends(get_db)):
    return db.query(models.Bill).order_by(models.Bill.id.desc()).all()


@router.get("/{bill_id}", response_model=schemas.BillResponse)
def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


@router.post("", response_model=schemas.BillResponse, status_code=201)
def create_bill(bill: schemas.BillCreate, db: Session = Depends(get_db)):
    if not bill.items:
        raise HTTPException(status_code=400, detail="Bill must have at least one item")

    # Validate stock for all items first
    resolved = []
    for line in bill.items:
        item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
        if item.quantity < line.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{item.name}': available {item.quantity}, requested {line.quantity}"
            )
        resolved.append((item, line))

    # Deduct stock
    for item, line in resolved:
        item.quantity -= line.quantity

    # Create bill
    db_bill = models.Bill(
        invoice_number="TMP",
        customer_name=bill.customer_name,
        customer_phone=bill.customer_phone,
        customer_type=bill.customer_type,
        status="paid",
        taxable_amount=0.0,
        igst_amount=0.0,
        total_amount=0.0,
    )
    db.add(db_bill)
    db.flush()

    db_bill.invoice_number = f"INV-{db_bill.id:04d}"

    taxable_total = 0.0
    igst_total = 0.0
    for item, line in resolved:
        taxable = round(line.quantity * line.unit_price, 2)
        gst_rate = item.gst_rate or 0.0
        igst = round(taxable * gst_rate / 100, 2)
        line_total = round(taxable + igst, 2)
        taxable_total += taxable
        igst_total += igst
        db.add(models.BillItem(
            bill_id=db_bill.id,
            item_id=item.id,
            item_name=item.name,
            hsn_code=item.hsn_code,
            unit=item.unit,
            quantity=line.quantity,
            unit_price=line.unit_price,
            gst_rate=gst_rate,
            taxable_amount=taxable,
            igst_amount=igst,
            line_total=line_total,
        ))

    db_bill.taxable_amount = round(taxable_total, 2)
    db_bill.igst_amount = round(igst_total, 2)
    db_bill.total_amount = round(taxable_total + igst_total, 2)
    db.commit()
    db.refresh(db_bill)
    return db_bill


@router.patch("/{bill_id}/cancel", response_model=schemas.BillResponse)
def cancel_bill(bill_id: int, db: Session = Depends(get_db)):
    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    if bill.status == "cancelled":
        raise HTTPException(status_code=400, detail="Bill is already cancelled")

    for line in bill.items:
        if line.item_id:
            item = db.query(models.Item).filter(models.Item.id == line.item_id).first()
            if item:
                item.quantity += line.quantity

    bill.status = "cancelled"
    db.commit()
    db.refresh(bill)
    return bill


@router.get("/{bill_id}/print", response_class=HTMLResponse)
def print_bill(bill_id: int, request: Request, db: Session = Depends(get_db)):
    bill = db.query(models.Bill).filter(models.Bill.id == bill_id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Build per-HSN tax summary rows
    hsn_map = {}
    for line in bill.items:
        key = (line.hsn_code or '', line.gst_rate or 0.0)
        if key not in hsn_map:
            hsn_map[key] = {"hsn": line.hsn_code or '', "gst_rate": line.gst_rate or 0.0, "taxable": 0.0}
        hsn_map[key]["taxable"] += line.taxable_amount

    tax_rows = []
    for (hsn, gst_rate), row in hsn_map.items():
        half = round(row["taxable"] * gst_rate / 100 / 2, 2)
        tax_rows.append({
            "hsn": hsn, "gst_rate": gst_rate,
            "taxable": round(row["taxable"], 2),
            "cgst": half, "sgst": half,
            "total_tax": round(half * 2, 2),
        })

    return _templates.TemplateResponse("print_invoice.html", {
        "request":      request,
        "bill":         bill,
        "company":      _COMPANY,
        "amount_words": amount_in_words(bill.total_amount),
        "tax_words":    amount_in_words(bill.igst_amount),
        "tax_rows":     tax_rows,
    })
