from decimal import Decimal
from fastapi import HTTPException
from app import models, schemas
from app.repositories.bill import BillRepository
from app.repositories.item import ItemRepository
from app.repositories.payment import PaymentRepository
from app.services.tax import calculate_line_tax


class BillService:
    def __init__(self, bill_repo: BillRepository, item_repo: ItemRepository, payment_repo: PaymentRepository):
        self.bill_repo = bill_repo
        self.item_repo = item_repo
        self.payment_repo = payment_repo

    @staticmethod
    def _derive_payment_state(bill: models.Bill) -> str:
        if bill.amount_paid <= 0:
            return "unpaid"
        if round(bill.amount_paid, 2) < round(bill.total_amount, 2):
            return "partially_paid"
        return "paid"

    def _record_payment(
        self,
        bill: models.Bill,
        amount: Decimal,
        method: str,
        reference: str | None = None,
        notes: str | None = None,
        payment_date=None,
    ) -> models.Payment:
        payment = models.Payment(
            bill_id=bill.id,
            amount=round(amount, 2),
            payment_method=method,
            reference_number=reference,
            notes=notes,
        )
        if payment_date is not None:
            payment.payment_date = payment_date
        self.payment_repo.save(payment)
        bill.amount_paid = round(bill.amount_paid + amount, 2)
        bill.payment_state = self._derive_payment_state(bill)
        return payment

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

        resolved = []
        for line in data.items:
            item = items_by_id.get(line.item_id)
            if not item:
                raise HTTPException(status_code=404, detail=f"Item id {line.item_id} not found")
            resolved.append((item, line))

        # Aggregate requested quantity per item BEFORE validating stock.
        # Two lines for the same item must be checked against their combined
        # demand, not validated independently against the same starting
        # stock level (which would let both pass and drive stock negative).
        required_by_item: dict[int, int] = {}
        for item, line in resolved:
            required_by_item[item.id] = required_by_item.get(item.id, 0) + line.quantity

        for item_id, required_qty in required_by_item.items():
            item = items_by_id[item_id]
            if item.quantity < required_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for '{item.name}': available {item.quantity}, requested {required_qty}",
                )

        # Create bill header (TMP number, replaced after flush gives us an id)
        db_bill = models.Bill(
            invoice_number="TMP",
            customer_name=data.customer_name,
            customer_phone=data.customer_phone,
            customer_type=data.customer_type,
            status="paid",
            taxable_amount=Decimal("0"),
            igst_amount=Decimal("0"),
            total_amount=Decimal("0"),
        )
        self.bill_repo.save(db_bill)
        db_bill.invoice_number = f"INV-{db_bill.id:04d}"

        taxable_total = Decimal("0")
        igst_total = Decimal("0")
        for item, line in resolved:
            self.item_repo.apply_stock_change(
                item, -line.quantity, "SALE",
                reference_type="bill", reference_id=db_bill.id,
                note=f"Sold via {db_bill.invoice_number}",
            )
            gst_rate = item.gst_rate or Decimal("0")
            tax = calculate_line_tax(line.quantity, line.unit_price, gst_rate)
            taxable_total += tax["taxable_amount"]
            igst_total += tax["tax_amount"]
            self.bill_repo.add_item(models.BillItem(
                bill_id=db_bill.id,
                item_id=item.id,
                item_name=item.name,
                hsn_code=item.hsn_code,
                unit=item.unit,
                quantity=line.quantity,
                unit_price=line.unit_price,
                gst_rate=gst_rate,
                taxable_amount=tax["taxable_amount"],
                igst_amount=tax["tax_amount"],
                line_total=tax["line_total"],
            ))

        db_bill.taxable_amount = round(taxable_total, 2)
        db_bill.igst_amount = round(igst_total, 2)
        db_bill.total_amount = round(taxable_total + igst_total, 2)

        # Payment collected at sale. Defaults to full total (preserves the
        # app's original cash-sale behavior) unless a smaller amount is given.
        requested_paid = data.amount_paid if data.amount_paid is not None else db_bill.total_amount
        if round(requested_paid, 2) > round(db_bill.total_amount, 2):
            raise HTTPException(
                status_code=400,
                detail=f"Amount paid (₹{requested_paid:.2f}) cannot exceed invoice total (₹{db_bill.total_amount:.2f})",
            )
        db_bill.due_date = data.due_date
        db_bill.amount_paid = Decimal("0")
        db_bill.payment_state = "unpaid"
        if requested_paid > 0:
            self._record_payment(
                db_bill, requested_paid, data.payment_method, data.payment_reference,
                notes="Recorded at sale",
            )

        self.bill_repo.commit()
        bill = self.bill_repo.refresh(db_bill)

        # Soft price-tier check — warn if any line price differs from the
        # standard price for this customer type (only when the tier price is set)
        price_field = self._TIER_PRICE_FIELD.get(data.customer_type or "retailer")
        warnings = []
        if price_field:
            for item, line in resolved:
                expected = getattr(item, price_field, None) or Decimal("0")
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
                self.item_repo.apply_stock_change(
                    item, line.quantity, "SALE_CANCEL",
                    reference_type="bill", reference_id=bill.id,
                    note=f"Reversed on cancellation of {bill.invoice_number}",
                )
            elif line.item_id:
                # Item existed when the bill was created but has since been deleted
                warnings.append(
                    f"'{line.item_name}' (qty {line.quantity}) — item has been deleted "
                    f"from inventory. This quantity could not be restored. "
                    f"Please adjust your stock records manually."
                )

        if bill.amount_paid > 0:
            warnings.append(
                f"This invoice had ₹{bill.amount_paid:.2f} recorded as paid. "
                f"Cancelling does not automatically refund or reverse this payment — "
                f"please process a refund manually if applicable."
            )

        bill.status = "cancelled"
        self.bill_repo.commit()
        return self.bill_repo.refresh(bill), warnings

    def get_payments(self, bill_id: int) -> list[models.Payment]:
        self.get_by_id(bill_id)  # 404 if missing
        return self.payment_repo.get_by_bill(bill_id)

    def add_payment(self, bill_id: int, data: schemas.PaymentCreate) -> models.Bill:
        bill = self.get_by_id(bill_id)
        if bill.status == "cancelled":
            raise HTTPException(status_code=400, detail="Cannot record a payment against a cancelled invoice")
        if round(bill.amount_paid + data.amount, 2) > round(bill.total_amount, 2):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Payment of ₹{data.amount:.2f} would exceed the outstanding balance "
                    f"of ₹{bill.balance_due:.2f} for {bill.invoice_number}"
                ),
            )
        self._record_payment(
            bill, data.amount, data.payment_method, data.reference_number,
            notes=data.notes, payment_date=data.payment_date,
        )
        self.bill_repo.commit()
        return self.bill_repo.refresh(bill)

    def cancel_payment(self, bill_id: int, payment_id: int) -> models.Bill:
        bill = self.get_by_id(bill_id)
        payment = self.payment_repo.get_by_id(payment_id)
        if not payment or payment.bill_id != bill_id:
            raise HTTPException(status_code=404, detail="Payment not found for this invoice")
        if payment.status == "cancelled":
            raise HTTPException(status_code=400, detail="Payment is already cancelled")

        payment.status = "cancelled"
        bill.amount_paid = round(bill.amount_paid - payment.amount, 2)
        bill.payment_state = self._derive_payment_state(bill)
        self.bill_repo.commit()
        return self.bill_repo.refresh(bill)
