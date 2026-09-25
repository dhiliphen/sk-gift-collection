from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import get_current_username
from app.audit import record
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.item import ItemRepository
from app.services.purchase_order import PurchaseOrderService

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


def get_service(db: Session = Depends(get_db)) -> PurchaseOrderService:
    return PurchaseOrderService(PurchaseOrderRepository(db), ItemRepository(db))


@router.get("", response_model=list[schemas.PurchaseOrderResponse])
def get_all_purchase_orders(service: PurchaseOrderService = Depends(get_service)):
    return service.get_all()


@router.get("/{order_id}", response_model=schemas.PurchaseOrderResponse)
def get_purchase_order(order_id: int, service: PurchaseOrderService = Depends(get_service)):
    return service.get_by_id(order_id)


@router.post("", response_model=schemas.PurchaseOrderResponse, status_code=201)
def create_purchase_order(
    order: schemas.PurchaseOrderCreate,
    db: Session = Depends(get_db),
    service: PurchaseOrderService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(order)
    record(db, username, "CREATE_PURCHASE_ORDER", "purchase_order", created.id,
           new_value=schemas.PurchaseOrderResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.patch("/{order_id}/confirm", response_model=schemas.PurchaseOrderResponse)
def confirm_purchase_order(
    order_id: int,
    db: Session = Depends(get_db),
    service: PurchaseOrderService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    updated = service.confirm(order_id)
    record(db, username, "CONFIRM_PURCHASE_ORDER", "purchase_order", order_id,
           new_value={"status": updated.status})
    return updated


@router.patch("/{order_id}/cancel", response_model=schemas.PurchaseOrderResponse)
def cancel_purchase_order(
    order_id: int,
    db: Session = Depends(get_db),
    service: PurchaseOrderService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old_status = service.get_by_id(order_id).status
    updated = service.cancel(order_id)
    record(db, username, "CANCEL_PURCHASE_ORDER", "purchase_order", order_id,
           old_value={"status": old_status}, new_value={"status": updated.status})
    return updated
