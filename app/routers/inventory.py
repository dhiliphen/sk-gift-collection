from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api", tags=["inventory"])


@router.get("/items", response_model=list[schemas.ItemResponse])
def get_all_items(
    category: Optional[str] = None,
    low_stock: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Item)
    if category:
        query = query.filter(models.Item.category == category)
    if low_stock:
        query = query.filter(models.Item.quantity <= models.Item.low_stock_threshold)
    return query.all()


@router.get("/items/{item_id}", response_model=schemas.ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/items", response_model=schemas.ItemResponse, status_code=201)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Item).filter(models.Item.name == item.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Item with this name already exists")
    db_item = models.Item(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/items/{item_id}", response_model=schemas.ItemResponse)
def update_item(item_id: int, item: schemas.ItemUpdate, db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in item.dict(exclude_unset=True).items():
        setattr(db_item, field, value)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.patch("/items/{item_id}/stock", response_model=schemas.ItemResponse)
def update_stock(item_id: int, payload: schemas.StockUpdate, db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    new_qty = db_item.quantity + payload.quantity_change
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Stock cannot go below zero")
    db_item.quantity = new_qty
    db.commit()
    db.refresh(db_item)
    return db_item


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    db_item = db.query(models.Item).filter(models.Item.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(db_item)
    db.commit()


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    items = db.query(models.Item).all()
    total_items = len(items)
    total_value = sum(i.quantity * i.cost_price for i in items)
    low_stock = [i for i in items if i.quantity <= i.low_stock_threshold]
    categories = list(set(i.category for i in items if i.category))
    return {
        "total_items": total_items,
        "total_value": round(total_value, 2),
        "low_stock_count": len(low_stock),
        "categories": categories,
    }
