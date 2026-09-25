import os
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.repositories.bill import BillRepository
from app.repositories.item import ItemRepository
from app.repositories.payment import PaymentRepository
from app.services.bill import BillService
from app.services.tax import split_cgst_sgst
from app.utils import amount_in_words

_base = os.environ.get('BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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


def get_service(db: Session = Depends(get_db)) -> BillService:
    return BillService(BillRepository(db), ItemRepository(db), PaymentRepository(db))


@router.get("", response_model=list[schemas.BillResponse])
def get_all_bills(service: BillService = Depends(get_service)):
    return service.get_all()


@router.get("/{bill_id}", response_model=schemas.BillResponse)
def get_bill(bill_id: int, service: BillService = Depends(get_service)):
    return service.get_by_id(bill_id)


@router.post("", response_model=schemas.BillResponse, status_code=201)
def create_bill(bill: schemas.BillCreate, service: BillService = Depends(get_service)):
    bill_obj, warnings = service.create(bill)
    data = schemas.BillResponse.model_validate(bill_obj).model_dump()
    data["warnings"] = warnings
    return data


@router.patch("/{bill_id}/cancel", response_model=schemas.BillCancelResponse)
def cancel_bill(bill_id: int, service: BillService = Depends(get_service)):
    bill, warnings = service.cancel(bill_id)
    return {"bill": bill, "warnings": warnings}


@router.get("/{bill_id}/payments", response_model=list[schemas.PaymentResponse])
def get_bill_payments(bill_id: int, service: BillService = Depends(get_service)):
    return service.get_payments(bill_id)


@router.post("/{bill_id}/payments", response_model=schemas.BillResponse, status_code=201)
def add_bill_payment(bill_id: int, payment: schemas.PaymentCreate, service: BillService = Depends(get_service)):
    bill = service.add_payment(bill_id, payment)
    data = schemas.BillResponse.model_validate(bill).model_dump()
    data["warnings"] = []
    return data


@router.patch("/{bill_id}/payments/{payment_id}/cancel", response_model=schemas.BillResponse)
def cancel_bill_payment(bill_id: int, payment_id: int, service: BillService = Depends(get_service)):
    bill = service.cancel_payment(bill_id, payment_id)
    data = schemas.BillResponse.model_validate(bill).model_dump()
    data["warnings"] = []
    return data


@router.get("/{bill_id}/print", response_class=HTMLResponse)
def print_bill(bill_id: int, request: Request, service: BillService = Depends(get_service)):
    bill = service.get_by_id(bill_id)

    hsn_map = {}
    for line in bill.items:
        key = (line.hsn_code or '', line.gst_rate or Decimal("0"))
        if key not in hsn_map:
            hsn_map[key] = {"hsn": line.hsn_code or '', "gst_rate": line.gst_rate or Decimal("0"), "taxable": Decimal("0")}
        hsn_map[key]["taxable"] += line.taxable_amount

    tax_rows = []
    for (hsn, gst_rate), row in hsn_map.items():
        split = split_cgst_sgst(row["taxable"], gst_rate)
        tax_rows.append({
            "hsn": hsn, "gst_rate": gst_rate,
            "taxable": round(row["taxable"], 2),
            "cgst": split["cgst"], "sgst": split["sgst"],
            "total_tax": split["total_tax"],
        })

    return _templates.TemplateResponse("print_invoice.html", {
        "request":      request,
        "bill":         bill,
        "company":      _COMPANY,
        "amount_words": amount_in_words(bill.total_amount),
        "tax_words":    amount_in_words(bill.igst_amount),
        "tax_rows":     tax_rows,
    })
