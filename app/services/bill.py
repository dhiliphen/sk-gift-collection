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

    def create(self, data: schemas.BillCreate) -> models.Bill:
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
        return self.bill_repo.refresh(db_bill)

    def cancel(self, bill_id: int) -> models.Bill:
        bill = self.get_by_id(bill_id)
        if bill.status == "cancelled":
            raise HTTPException(status_code=400, detail="Bill is already cancelled")

        # Batch-fetch items that need stock restored
        item_ids = [line.item_id for line in bill.items if line.item_id]
        items_by_id = self.item_repo.get_by_ids(item_ids)

        for line in bill.items:
            item = items_by_id.get(line.item_id)
            if item:
                item.quantity += line.quantity

        bill.status = "cancelled"
        self.bill_repo.commit()
        return self.bill_repo.refresh(bill)
