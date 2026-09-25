from decimal import Decimal
from fastapi import HTTPException
from app import models, schemas
from app.repositories.purchase_return import PurchaseReturnRepository
from app.repositories.purchase import PurchaseRepository
from app.repositories.item import ItemRepository


class PurchaseReturnService:
    def __init__(
        self,
        return_repo: PurchaseReturnRepository,
        purchase_repo: PurchaseRepository,
        item_repo: ItemRepository,
    ):
        self.return_repo = return_repo
        self.purchase_repo = purchase_repo
        self.item_repo = item_repo

    def get_by_purchase(self, purchase_id: int) -> list[models.PurchaseReturn]:
        return self.return_repo.get_by_purchase(purchase_id)

    def get_by_id(self, return_id: int) -> models.PurchaseReturn:
        ret = self.return_repo.get_with_items(return_id)
        if not ret:
            raise HTTPException(status_code=404, detail="Purchase return not found")
        return ret

    def create(self, purchase_id: int, data: schemas.PurchaseReturnCreate) -> tuple[models.PurchaseReturn, list[str]]:
        if not data.items:
            raise HTTPException(status_code=400, detail="Return must have at least one item")

        pb = self.purchase_repo.get_with_items(purchase_id)
        if not pb:
            raise HTTPException(status_code=404, detail="Purchase bill not found")
        if pb.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot return items from a cancelled purchase")

        purchase_items_by_id = {pi.id: pi for pi in pb.items}

        # Aggregate by purchase line first (cap against what was actually
        # bought on that line, minus what's already gone back).
        requested: dict[int, int] = {}
        for line in data.items:
            requested[line.purchase_item_id] = requested.get(line.purchase_item_id, 0) + line.quantity

        resolved = []
        for purchase_item_id, qty in requested.items():
            pi = purchase_items_by_id.get(purchase_item_id)
            if not pi:
                raise HTTPException(status_code=404, detail=f"Purchase line {purchase_item_id} not found on this purchase")
            remaining = pi.quantity - pi.quantity_returned
            if qty > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot return {qty} of '{pi.item_name}' — only {remaining} remaining "
                        f"(received {pi.quantity}, already returned {pi.quantity_returned})"
                    ),
                )
            resolved.append((pi, qty))

        # Separately aggregate by underlying item_id: two different purchase
        # lines could reference the same item, and stock only has one pool —
        # returning more than is currently on hand must be blocked in total,
        # not line by line (the same class of bug fixed for bill creation).
        item_ids = [pi.item_id for pi, _ in resolved if pi.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        required_by_item: dict[int, int] = {}
        for pi, qty in resolved:
            if pi.item_id:
                required_by_item[pi.item_id] = required_by_item.get(pi.item_id, 0) + qty

        for item_id, required_qty in required_by_item.items():
            item = items_by_id.get(item_id)
            if item and item.quantity < required_qty:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot return {required_qty} of '{item.name}' to the supplier — only "
                        f"{item.quantity} currently in stock"
                    ),
                )

        db_return = models.PurchaseReturn(
            debit_note_number="TMP",
            purchase_id=pb.id,
            supplier_name=pb.supplier_name,
            reason=data.reason,
            status="issued",
            total_amount=Decimal("0"),
        )
        self.return_repo.save(db_return)
        db_return.debit_note_number = f"DN-{db_return.id:04d}"

        warnings = []
        total = Decimal("0")
        for pi, qty in resolved:
            line_total = round(qty * pi.unit_cost, 2)
            total += line_total
            pi.quantity_returned += qty

            item = items_by_id.get(pi.item_id) if pi.item_id else None
            if item:
                self.item_repo.apply_stock_change(
                    item, -qty, "PURCHASE_RETURN",
                    reference_type="purchase_return", reference_id=db_return.id,
                    note=f"Returned to supplier via {db_return.debit_note_number}",
                )
            elif pi.item_id:
                warnings.append(
                    f"'{pi.item_name}' (qty {qty}) — item has been deleted from inventory. "
                    f"This quantity could not be deducted from stock. Please adjust manually."
                )

            self.return_repo.add_item(models.PurchaseReturnItem(
                return_id=db_return.id,
                purchase_item_id=pi.id,
                item_id=pi.item_id,
                item_name=pi.item_name,
                quantity=qty,
                unit_cost=pi.unit_cost,
                line_total=line_total,
            ))

        db_return.total_amount = round(total, 2)
        self.return_repo.commit()
        return self.return_repo.refresh(db_return), warnings

    def cancel(self, return_id: int) -> models.PurchaseReturn:
        """Voids a mistakenly recorded return, restoring the stock that was
        sent back to the supplier and the purchase line's returned-quantity
        tracking."""
        ret = self.get_by_id(return_id)
        if ret.status == "cancelled":
            raise HTTPException(status_code=400, detail="This return is already cancelled")

        item_ids = [line.item_id for line in ret.items if line.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        purchase_items_by_id = {pi.id: pi for pi in ret.purchase.items}
        for line in ret.items:
            pi = purchase_items_by_id.get(line.purchase_item_id)
            if pi:
                pi.quantity_returned = max(0, pi.quantity_returned - line.quantity)
            item = items_by_id.get(line.item_id)
            if item:
                self.item_repo.apply_stock_change(
                    item, line.quantity, "PURCHASE_RETURN",
                    reference_type="purchase_return", reference_id=ret.id,
                    note=f"Reversed on cancellation of {ret.debit_note_number}",
                )

        ret.status = "cancelled"
        self.return_repo.commit()
        return self.return_repo.refresh(ret)
