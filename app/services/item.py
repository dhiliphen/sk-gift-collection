from typing import Optional
from fastapi import HTTPException
from app import models, schemas
from app.repositories.item import ItemRepository


class ItemService:
    def __init__(self, repo: ItemRepository):
        self.repo = repo

    def get_all(
        self,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None,
    ) -> list[models.Item]:
        return self.repo.get_filtered(category=category, low_stock=low_stock)

    def get_by_id(self, item_id: int) -> models.Item:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

    def create(self, data: schemas.ItemCreate) -> models.Item:
        if self.repo.get_by_name(data.name):
            raise HTTPException(status_code=400, detail="Item with this name already exists")
        item = models.Item(**data.model_dump())
        self.repo.save(item)
        self.repo.commit()
        return self.repo.refresh(item)

    def update(self, item_id: int, data: schemas.ItemUpdate) -> models.Item:
        item = self.get_by_id(item_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        self.repo.commit()
        return self.repo.refresh(item)

    def update_stock(self, item_id: int, quantity_change: int) -> models.Item:
        item = self.get_by_id(item_id)
        new_qty = item.quantity + quantity_change
        if new_qty < 0:
            raise HTTPException(status_code=400, detail="Stock cannot go below zero")
        item.quantity = new_qty
        self.repo.commit()
        return self.repo.refresh(item)

    def delete(self, item_id: int) -> None:
        item = self.get_by_id(item_id)
        self.repo.delete(item)
        self.repo.commit()

    def get_stats(self) -> dict:
        return self.repo.get_stats()
