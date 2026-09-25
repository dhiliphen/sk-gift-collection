import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import get_current_username
from app.audit import record
from app.repositories.purchase import PurchaseRepository
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.item import ItemRepository
from app.services.purchase import PurchaseService
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

router = APIRouter(prefix="/api/purchases", tags=["purchases"])


def get_service(db: Session = Depends(get_db)) -> PurchaseService:
    return PurchaseService(PurchaseRepository(db), ItemRepository(db), PurchaseOrderRepository(db))


@router.get("", response_model=list[schemas.PurchaseResponse])
def get_all_purchases(service: PurchaseService = Depends(get_service)):
    return service.get_all()


@router.get("/{purchase_id}", response_model=schemas.PurchaseResponse)
def get_purchase(purchase_id: int, service: PurchaseService = Depends(get_service)):
    return service.get_by_id(purchase_id)


@router.post("", response_model=schemas.PurchaseResponse, status_code=201)
def create_purchase(
    purchase: schemas.PurchaseCreate,
    db: Session = Depends(get_db),
    service: PurchaseService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(purchase)
    record(db, username, "CREATE_PURCHASE", "purchase", created.id,
           new_value=schemas.PurchaseResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.patch("/{purchase_id}/cancel", response_model=schemas.PurchaseCancelResponse)
def cancel_purchase(
    purchase_id: int,
    db: Session = Depends(get_db),
    service: PurchaseService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.PurchaseResponse.model_validate(service.get_by_id(purchase_id)).model_dump(mode="json")
    purchase, warnings = service.cancel(purchase_id)
    record(db, username, "CANCEL_PURCHASE", "purchase", purchase_id,
           old_value=old, new_value=schemas.PurchaseResponse.model_validate(purchase).model_dump(mode="json"))
    return {"purchase": purchase, "warnings": warnings}


@router.get("/{purchase_id}/print", response_class=HTMLResponse)
def print_purchase(purchase_id: int, request: Request, service: PurchaseService = Depends(get_service)):
    pb = service.get_by_id(purchase_id)
    return _templates.TemplateResponse("print_purchase.html", {
        "request":      request,
        "purchase":     pb,
        "company":      _COMPANY,
        "amount_words": amount_in_words(pb.total_amount),
    })
