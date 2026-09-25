from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import schemas
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
def create_item(item: schemas.ItemCreate, service: ItemService = Depends(get_service)):
    return service.create(item)


@router.put("/items/{item_id}", response_model=schemas.ItemResponse)
def update_item(item_id: int, item: schemas.ItemUpdate, service: ItemService = Depends(get_service)):
    return service.update(item_id, item)


@router.patch("/items/{item_id}/stock", response_model=schemas.ItemResponse)
def update_stock(item_id: int, payload: schemas.StockUpdate, service: ItemService = Depends(get_service)):
    return service.update_stock(item_id, payload.quantity_change)


@router.get("/items/{item_id}/movements", response_model=list[schemas.StockMovementResponse])
def get_item_movements(item_id: int, service: ItemService = Depends(get_service)):
    return service.get_movements(item_id)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, service: ItemService = Depends(get_service)):
    service.delete(item_id)


@router.get("/stats")
def get_stats(service: ItemService = Depends(get_service)):
    return service.get_stats()
