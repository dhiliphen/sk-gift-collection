from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
from app.auth import get_current_username
from app.audit import record
from app.repositories.item import ItemRepository
from app.services.item import ItemService

router = APIRouter(prefix="/api", tags=["inventory"])


def get_service(db: Session = Depends(get_db)) -> ItemService:
    return ItemService(ItemRepository(db))


@router.get("/items", response_model=list[schemas.ItemResponse])
def get_all_items(
    category: Optional[str] = None,
    low_stock: Optional[bool] = None,
    service: ItemService = Depends(get_service),
):
    return service.get_all(category=category, low_stock=low_stock)


@router.get("/items/{item_id}", response_model=schemas.ItemResponse)
def get_item(item_id: int, service: ItemService = Depends(get_service)):
    return service.get_by_id(item_id)


@router.post("/items", response_model=schemas.ItemResponse, status_code=201)
def create_item(
    item: schemas.ItemCreate,
    db: Session = Depends(get_db),
    service: ItemService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    created = service.create(item)
    record(db, username, "CREATE_ITEM", "item", created.id,
           new_value=schemas.ItemResponse.model_validate(created).model_dump(mode="json"))
    return created


@router.put("/items/{item_id}", response_model=schemas.ItemResponse)
def update_item(
    item_id: int,
    item: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    service: ItemService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.ItemResponse.model_validate(service.get_by_id(item_id)).model_dump(mode="json")
    updated = service.update(item_id, item)
    record(db, username, "UPDATE_ITEM", "item", item_id,
           old_value=old, new_value=schemas.ItemResponse.model_validate(updated).model_dump(mode="json"))
    return updated


@router.patch("/items/{item_id}/stock", response_model=schemas.ItemResponse)
def update_stock(
    item_id: int,
    payload: schemas.StockUpdate,
    db: Session = Depends(get_db),
    service: ItemService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old_qty = service.get_by_id(item_id).quantity
    updated = service.update_stock(item_id, payload.quantity_change)
    record(db, username, "STOCK_ADJUSTMENT", "item", item_id,
           old_value={"quantity": old_qty}, new_value={"quantity": updated.quantity})
    return updated


@router.get("/items/{item_id}/movements", response_model=list[schemas.StockMovementResponse])
def get_item_movements(item_id: int, service: ItemService = Depends(get_service)):
    return service.get_movements(item_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    service: ItemService = Depends(get_service),
    username: str = Depends(get_current_username),
):
    old = schemas.ItemResponse.model_validate(service.get_by_id(item_id)).model_dump(mode="json")
    service.delete(item_id)
    record(db, username, "DELETE_ITEM", "item", item_id, old_value=old)


@router.get("/stats")
def get_stats(service: ItemService = Depends(get_service)):
    return service.get_stats()
