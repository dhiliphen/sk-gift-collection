from decimal import Decimal
from fastapi import HTTPException
from app import models, schemas
from app.repositories.purchase_order import PurchaseOrderRepository
from app.repositories.item import ItemRepository


class PurchaseOrderService:
    def __init__(self, order_repo: PurchaseOrderRepository, item_repo: ItemRepository):
        self.order_repo = order_repo
        self.item_repo = item_repo

    def get_all(self) -> list[models.PurchaseOrder]:
        return self.order_repo.get_all_ordered()

    def get_by_id(self, order_id: int) -> models.PurchaseOrder:
        order = self.order_repo.get_with_items(order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        return order

    def create(self, data: schemas.PurchaseOrderCreate) -> models.PurchaseOrder:
        if not data.items:
            raise HTTPException(status_code=400, detail="Purchase order must have at least one item")

        item_ids = [line.item_id for line in data.items]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        resolved = []
        for line in data.items:
            item = items_by_id.get(line.item_id)
            if not item:
                raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
            resolved.append((item, line))

        # No stock impact here — creating (or confirming) a PO never touches
        # inventory. Stock only changes when a goods receipt is recorded.
        db_order = models.PurchaseOrder(
            po_number="TMP",
            supplier_name=data.supplier_name,
            expected_delivery_date=data.expected_delivery_date,
            notes=data.notes,
            status="DRAFT",
            total_amount=Decimal("0"),
        )
        self.order_repo.save(db_order)
        db_order.po_number = f"PO-{db_order.id:04d}"

        total = Decimal("0")
        for item, line in resolved:
            line_total = round(line.quantity * line.unit_cost, 2)
            total += line_total
            self.order_repo.add_item(models.PurchaseOrderItem(
                order_id=db_order.id,
                item_id=item.id,
                item_name=item.name,
                unit=item.unit,
                quantity_ordered=line.quantity,
                unit_cost=line.unit_cost,
                line_total=line_total,
            ))

        db_order.total_amount = round(total, 2)
        self.order_repo.commit()
        return self.order_repo.refresh(db_order)

    def confirm(self, order_id: int) -> models.PurchaseOrder:
        order = self.get_by_id(order_id)
        if order.status != "DRAFT":
            raise HTTPException(status_code=400, detail=f"Only a DRAFT order can be confirmed (this one is {order.status})")
        order.status = "CONFIRMED"
        self.order_repo.commit()
        return self.order_repo.refresh(order)

    def cancel(self, order_id: int) -> models.PurchaseOrder:
        order = self.get_by_id(order_id)
        if order.status not in ("DRAFT", "CONFIRMED"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel a {order.status.replace('_', ' ').lower()} order — goods have already been received against it",
            )
        order.status = "CANCELLED"
        self.order_repo.commit()
        return self.order_repo.refresh(order)
