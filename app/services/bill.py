from fastapi import HTTPException
from app import models, schemas
from app.repositories.bill import BillRepository
from app.repositories.item import ItemRepository


class BillService:
    def __init__(self, bill_repo: BillRepository, item_repo: ItemRepository):
        self.bill_repo = bill_repo
        self.item_repo = item_repo

    def get_all(self) -> list[models.Bill]:
        return self.bill_repo.get_all_ordered()

    def get_by_id(self, bill_id: int) -> models.Bill:
        bill = self.bill_repo.get_with_items(bill_id)
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        return bill

    # Maps customer_type to the item attribute that holds the standard price for that tier
    _TIER_PRICE_FIELD = {
        "retailer":   "selling_price",
        "dealer":     "dealer_price",
        "wholesaler": "wholesale_price",
    }

    def create(self, data: schemas.BillCreate) -> tuple[models.Bill, list[str]]:
        if not data.items:
            raise HTTPException(status_code=400, detail="Bill must have at least one item")

        # Batch-fetch all items in one query
        item_ids = [line.item_id for line in data.items]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        # Validate stock for every line before touching anything
        resolved = []
        for line in data.items:
            item = items_by_id.get(line.item_id)
            if not item:
                raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
            if item.quantity < line.quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for '{item.name}': available {item.quantity}, requested {line.quantity}",
                )
            resolved.append((item, line))

        # Deduct stock
        for item, line in resolved:
            item.quantity -= line.quantity

        # Create bill header (TMP number, replaced after flush gives us an id)
        db_bill = models.Bill(
            invoice_number="TMP",
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            customer_type=data.customer_type,
            status="paid",
            taxable_amount=0.0,
            igst_amount=0.0,
            total_amount=0.0,
        )
        self.bill_repo.save(db_bill)
        db_bill.invoice_number = f"INV-{db_bill.id:04d}"

        taxable_total = 0.0
        igst_total = 0.0
        for item, line in resolved:
            taxable = round(line.quantity * line.unit_price, 2)
            gst_rate = item.gst_rate or 0.0
            igst = round(taxable * gst_rate / 100, 2)
            taxable_total += taxable
            igst_total += igst
            self.bill_repo.add_item(models.BillItem(
                bill_id=db_bill.id,
                item_id=item.id,
                item_name=item.name,
                hsn_code=item.hsn_code,
                unit=item.unit,
                quantity=line.quantity,
                unit_price=line.unit_price,
                gst_rate=gst_rate,
                taxable_amount=taxable,
                igst_amount=igst,
                line_total=round(taxable + igst, 2),
            ))

        db_bill.taxable_amount = round(taxable_total, 2)
        db_bill.igst_amount = round(igst_total, 2)
        db_bill.total_amount = round(taxable_total + igst_total, 2)

        self.bill_repo.commit()
        bill = self.bill_repo.refresh(db_bill)

        # Soft price-tier check — warn if any line price differs from the
        # standard price for this customer type (only when the tier price is set)
        price_field = self._TIER_PRICE_FIELD.get(data.customer_type or "retailer")
        warnings = []
        if price_field:
            for item, line in resolved:
                expected = getattr(item, price_field, 0.0) or 0.0
                if expected > 0 and round(line.unit_price, 2) != round(expected, 2):
                    warnings.append(
                        f"'{item.name}': billed at ₹{line.unit_price:.2f} but standard "
                        f"{data.customer_type} price is ₹{expected:.2f}."
                    )

        return bill, warnings

    def cancel(self, bill_id: int) -> tuple[models.Bill, list[str]]:
        """Returns (bill, warnings). warnings lists any line items whose inventory
        item has been deleted — those quantities could not be restored."""
        bill = self.get_by_id(bill_id)
        if bill.status == "cancelled":
            raise HTTPException(status_code=400, detail="Bill is already cancelled")

        # Batch-fetch items that need stock restored
        item_ids = [line.item_id for line in bill.items if line.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        warnings = []
        for line in bill.items:
            item = items_by_id.get(line.item_id)
            if item:
                item.quantity += line.quantity
            elif line.item_id:
                # Item existed when the bill was created but has since been deleted
                warnings.append(
                    f"'{line.item_name}' (qty {line.quantity}) — item has been deleted "
                    f"from inventory. This quantity could not be restored. "
                    f"Please adjust your stock records manually."
                )

        bill.status = "cancelled"
        self.bill_repo.commit()
        return self.bill_repo.refresh(bill), warnings
