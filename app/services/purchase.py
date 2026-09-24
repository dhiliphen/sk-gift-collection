from fastapi import HTTPException
from app import models, schemas
from app.repositories.purchase import PurchaseRepository
from app.repositories.item import ItemRepository


class PurchaseService:
    def __init__(self, purchase_repo: PurchaseRepository, item_repo: ItemRepository):
        self.purchase_repo = purchase_repo
        self.item_repo = item_repo

    def get_all(self) -> list[models.PurchaseBill]:
        return self.purchase_repo.get_all_ordered()

    def get_by_id(self, purchase_id: int) -> models.PurchaseBill:
        pb = self.purchase_repo.get_with_items(purchase_id)
        if not pb:
            raise HTTPException(status_code=404, detail="Purchase bill not found")
        return pb

    def create(self, data: schemas.PurchaseCreate) -> models.PurchaseBill:
        if not data.items:
            raise HTTPException(status_code=400, detail="Purchase must have at least one item")

        # Batch-fetch all referenced items in one query
        item_ids = [line.item_id for line in data.items]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        resolved = []
        for line in data.items:
            item = items_by_id.get(line.item_id)
            if not item:
                raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
            resolved.append((item, line))

        db_bill = models.PurchaseBill(
            purchase_number="TMP",
            supplier_name=data.supplier_name,
            supplier_invoice=data.supplier_invoice,
            status="received",
            total_amount=0.0,
        )
        self.purchase_repo.save(db_bill)
        db_bill.purchase_number = f"PUR-{db_bill.id:04d}"

        total = 0.0
        for item, line in resolved:
            line_total = round(line.quantity * line.unit_cost, 2)
            total += line_total
            item.quantity += line.quantity
            self.purchase_repo.add_item(models.PurchaseBillItem(
                bill_id=db_bill.id,
                item_id=item.id,
                item_name=item.name,
                unit=item.unit,
                quantity=line.quantity,
                unit_cost=line.unit_cost,
                line_total=line_total,
            ))

        db_bill.total_amount = round(total, 2)
        self.purchase_repo.commit()
        return self.purchase_repo.refresh(db_bill)

    def cancel(self, purchase_id: int) -> models.PurchaseBill:
        pb = self.get_by_id(purchase_id)
        if pb.status == "cancelled":
            raise HTTPException(status_code=400, detail="Already cancelled")

        # Batch-fetch items that need stock deducted
        item_ids = [line.item_id for line in pb.items if line.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        # Block cancellation if any purchased stock has already been consumed by sales.
        # If current stock < quantity originally purchased, reversing would make stock
        # negative — meaning those units were already sold. The stock trail would break.
        consumed = []
        for line in pb.items:
            item = items_by_id.get(line.item_id)
            if item and item.quantity < line.quantity:
                consumed.append(
                    f"'{item.name}': purchased {line.quantity}, only {item.quantity} remaining"
                )

        if consumed:
            detail = (
                f"Cannot cancel {pb.purchase_number} — stock has been partially or fully "
                f"consumed by sales: {'; '.join(consumed)}. "
                f"Please verify the stock trail before cancelling."
            )
            raise HTTPException(status_code=409, detail=detail)

        for line in pb.items:
            item = items_by_id.get(line.item_id)
            if item:
                item.quantity -= line.quantity

        pb.status = "cancelled"
        self.purchase_repo.commit()
        return self.purchase_repo.refresh(pb)
