from typing import Optional
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from app import models
from app.repositories.base import BaseRepository


class ItemRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(models.Item, db)

    def get_by_name(self, name: str) -> Optional[models.Item]:
        return self.db.query(models.Item).filter(models.Item.name == name).first()

    def get_filtered(
        self,
        category: Optional[str] = None,
        low_stock: Optional[bool] = None,
    ) -> list[models.Item]:
        q = self.db.query(models.Item)
        if category:
            q = q.filter(models.Item.category == category)
        if low_stock:
            q = q.filter(models.Item.quantity <= models.Item.low_stock_threshold)
        return q.all()

    def get_by_ids(self, ids: list[int]) -> dict[int, models.Item]:
        """Batch fetch items by a list of IDs. Returns a {id: Item} map."""
        items = self.db.query(models.Item).filter(models.Item.id.in_(ids)).all()
        return {item.id: item for item in items}

    def apply_stock_change(
        self,
        item: models.Item,
        quantity_change: int,
        movement_type: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> models.StockMovement:
        """Adjusts item.quantity and records the change in the stock ledger
        as a single unit of work. Caller is responsible for validating the
        change beforehand (e.g. no-negative-stock) and committing."""
        quantity_before = item.quantity
        item.quantity = quantity_before + quantity_change
        movement = models.StockMovement(
            item_id=item.id,
            movement_type=movement_type,
            quantity_change=quantity_change,
            quantity_before=quantity_before,
            quantity_after=item.quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
        )
        self.db.add(movement)
        self.db.flush()
        return movement

    def get_movements(self, item_id: int) -> list[models.StockMovement]:
        return (
            self.db.query(models.StockMovement)
            .filter(models.StockMovement.item_id == item_id)
            .order_by(models.StockMovement.id.asc())
            .all()
        )

    def get_stats(self) -> dict:
        """Single SQL query for dashboard stats — no Python-side aggregation."""
        row = self.db.query(
            func.count(models.Item.id).label("total_items"),
            func.coalesce(
                func.sum(models.Item.quantity * models.Item.cost_price), 0
            ).label("total_value"),
            func.coalesce(
                func.sum(
                    case((models.Item.quantity <= models.Item.low_stock_threshold, 1), else_=0)
                ), 0
            ).label("low_stock_count"),
            func.coalesce(
                func.sum(case((models.Item.quantity == 0, 1), else_=0)), 0
            ).label("out_of_stock_count"),
        ).one()

        categories = [
            r[0]
            for r in self.db.query(models.Item.category)
            .filter(models.Item.category.isnot(None))
            .distinct()
            .all()
        ]

        return {
            "total_items": row.total_items,
            "total_value": round(float(row.total_value), 2),
            "low_stock_count": row.low_stock_count,
            "out_of_stock_count": row.out_of_stock_count,
            "categories": categories,
        }
