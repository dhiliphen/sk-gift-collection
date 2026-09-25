from decimal import Decimal
from fastapi import HTTPException
from app import models, schemas
from app.repositories.sales_return import SalesReturnRepository
from app.repositories.bill import BillRepository
from app.repositories.item import ItemRepository
from app.services.tax import calculate_line_tax


class SalesReturnService:
    def __init__(
        self,
        return_repo: SalesReturnRepository,
        bill_repo: BillRepository,
        item_repo: ItemRepository,
    ):
        self.return_repo = return_repo
        self.bill_repo = bill_repo
        self.item_repo = item_repo

    def get_by_bill(self, bill_id: int) -> list[models.SalesReturn]:
        return self.return_repo.get_by_bill(bill_id)

    def get_by_id(self, return_id: int) -> models.SalesReturn:
        ret = self.return_repo.get_with_items(return_id)
        if not ret:
            raise HTTPException(status_code=404, detail="Sales return not found")
        return ret

    def create(self, bill_id: int, data: schemas.SalesReturnCreate) -> tuple[models.SalesReturn, list[str]]:
        if not data.items:
            raise HTTPException(status_code=400, detail="Return must have at least one item")

        bill = self.bill_repo.get_with_items(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        if bill.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot return items from a cancelled invoice")

        bill_items_by_id = {bi.id: bi for bi in bill.items}

        # Aggregate requested return quantity per line BEFORE validating —
        # two entries for the same bill line must be checked against their
        # combined total, not independently.
        requested: dict[int, int] = {}
        for line in data.items:
            requested[line.bill_item_id] = requested.get(line.bill_item_id, 0) + line.quantity

        resolved = []
        for bill_item_id, qty in requested.items():
            bi = bill_items_by_id.get(bill_item_id)
            if not bi:
                raise HTTPException(status_code=404, detail=f"Bill line {bill_item_id} not found on this invoice")
            remaining = bi.quantity - bi.quantity_returned
            if qty > remaining:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot return {qty} of '{bi.item_name}' — only {remaining} remaining "
                        f"(billed {bi.quantity}, already returned {bi.quantity_returned})"
                    ),
                )
            resolved.append((bi, qty))

        item_ids = [bi.item_id for bi, _ in resolved if bi.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        db_return = models.SalesReturn(
            credit_note_number="TMP",
            bill_id=bill.id,
            customer_name=bill.customer_name,
            reason=data.reason,
            status="issued",
            taxable_amount=Decimal("0"),
            igst_amount=Decimal("0"),
            total_amount=Decimal("0"),
        )
        self.return_repo.save(db_return)
        db_return.credit_note_number = f"CRN-{db_return.id:04d}"

        warnings = []
        taxable_total = Decimal("0")
        igst_total = Decimal("0")
        for bi, qty in resolved:
            tax = calculate_line_tax(qty, bi.unit_price, bi.gst_rate or Decimal("0"))
            taxable_total += tax["taxable_amount"]
            igst_total += tax["tax_amount"]
            bi.quantity_returned += qty

            item = items_by_id.get(bi.item_id) if bi.item_id else None
            if item:
                self.item_repo.apply_stock_change(
                    item, qty, "SALES_RETURN",
                    reference_type="sales_return", reference_id=db_return.id,
                    note=f"Returned via {db_return.credit_note_number}",
                )
            elif bi.item_id:
                warnings.append(
                    f"'{bi.item_name}' (qty {qty}) — item has been deleted from inventory. "
                    f"This quantity could not be added back to stock. Please adjust manually."
                )

            self.return_repo.add_item(models.SalesReturnItem(
                return_id=db_return.id,
                bill_item_id=bi.id,
                item_id=bi.item_id,
                item_name=bi.item_name,
                quantity=qty,
                unit_price=bi.unit_price,
                gst_rate=bi.gst_rate,
                taxable_amount=tax["taxable_amount"],
                igst_amount=tax["tax_amount"],
                line_total=tax["line_total"],
            ))

        db_return.taxable_amount = round(taxable_total, 2)
        db_return.igst_amount = round(igst_total, 2)
        db_return.total_amount = round(taxable_total + igst_total, 2)

        self.return_repo.commit()
        return self.return_repo.refresh(db_return), warnings

    def cancel(self, return_id: int) -> models.SalesReturn:
        """Voids a mistakenly recorded return. Blocked if the stock that
        came back in has since been sold again — mirrors the existing
        purchase-cancellation-after-consumption guard."""
        ret = self.get_by_id(return_id)
        if ret.status == "cancelled":
            raise HTTPException(status_code=400, detail="This return is already cancelled")

        item_ids = [line.item_id for line in ret.items if line.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        consumed = []
        for line in ret.items:
            item = items_by_id.get(line.item_id)
            if item and item.quantity < line.quantity:
                consumed.append(f"'{item.name}': returned {line.quantity}, only {item.quantity} remaining")
        if consumed:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot cancel {ret.credit_note_number} — this stock has already been sold "
                    f"again: {'; '.join(consumed)}."
                ),
            )

        bill_items_by_id = {bi.id: bi for bi in ret.bill.items}
        for line in ret.items:
            bi = bill_items_by_id.get(line.bill_item_id)
            if bi:
                bi.quantity_returned = max(0, bi.quantity_returned - line.quantity)
            item = items_by_id.get(line.item_id)
            if item:
                self.item_repo.apply_stock_change(
                    item, -line.quantity, "SALES_RETURN",
                    reference_type="sales_return", reference_id=ret.id,
                    note=f"Reversed on cancellation of {ret.credit_note_number}",
                )

        ret.status = "cancelled"
        self.return_repo.commit()
        return self.return_repo.refresh(ret)
