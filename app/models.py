from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Fixed-precision type for all money and rate columns. SQLAlchemy's sqlite
# dialect stores Numeric values as text and returns Python Decimal on read,
# so amounts never pass through binary float representation.
MONEY = Numeric(12, 2)


class PurchaseBill(Base):
    __tablename__ = "purchase_bills"

    id = Column(Integer, primary_key=True, index=True)
    purchase_number = Column(String(20), unique=True, nullable=False, index=True)
    supplier_name = Column(String(100), nullable=False)
    supplier_invoice = Column(String(50), nullable=True)   # supplier's own ref number
    status = Column(String(20), default="received")        # received | cancelled
    total_amount = Column(MONEY, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("PurchaseBillItem", back_populates="bill", cascade="all, delete-orphan")


class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("purchase_bills.id"), nullable=False)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String(100), nullable=False)
    unit = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(MONEY, nullable=False)
    line_total = Column(MONEY, nullable=False)

    bill = relationship("PurchaseBill", back_populates="items")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    customer_type = Column(String(20), nullable=False)  # wholesaler | dealer | retailer
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Bill(Base):
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(20), unique=True, nullable=False, index=True)
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=True)
    status = Column(String(20), default="paid")  # paid | cancelled — document lifecycle, NOT payment state
    customer_type = Column(String(20), default="retailer")  # wholesaler | dealer | retailer
    taxable_amount = Column(MONEY, default=0)
    igst_amount = Column(MONEY, default=0)
    total_amount = Column(MONEY, default=0)
    amount_paid = Column(MONEY, default=0, nullable=False)
    # payment_state: unpaid | partially_paid | paid — reflects money actually
    # received. "overdue" and "cancelled" are derived at read time, not stored,
    # so they never go stale as time passes without a write.
    payment_state = Column(String(20), default="paid", nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="bill", cascade="all, delete-orphan")

    @property
    def balance_due(self):
        return round(self.total_amount - self.amount_paid, 2)

    @property
    def payment_status(self) -> str:
        """Read-time derived status: unpaid | partially_paid | paid | overdue | cancelled."""
        if self.status == "cancelled":
            return "cancelled"
        if self.payment_state != "paid" and self.due_date is not None:
            now = datetime.now(timezone.utc) if self.due_date.tzinfo else datetime.utcnow()
            if self.due_date < now:
                return "overdue"
        return self.payment_state


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    item_id = Column(Integer, nullable=True)   # snapshot; item may be deleted later
    item_name = Column(String(100), nullable=False)
    hsn_code = Column(String(20), nullable=True)
    unit = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(MONEY, nullable=False)
    gst_rate = Column(MONEY, default=0)
    taxable_amount = Column(MONEY, nullable=False)
    igst_amount = Column(MONEY, default=0)
    line_total = Column(MONEY, nullable=False)

    bill = relationship("Bill", back_populates="items")


class Payment(Base):
    """Append-only ledger of payments received against a bill.
    Bill.amount_paid is a cached running total kept in sync with this table."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False, index=True)
    amount = Column(MONEY, nullable=False)
    payment_method = Column(String(20), nullable=False, default="cash")
    reference_number = Column(String(50), nullable=True)
    notes = Column(String(255), nullable=True)
    status = Column(String(20), default="recorded")  # recorded | cancelled
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bill = relationship("Bill", back_populates="payments")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)


class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(20), unique=True, nullable=False, index=True)


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    contact_person = Column(String(100), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    address = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Item(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=True)
    supplier = Column(String(100), nullable=True)
    quantity = Column(Integer, default=0, nullable=False)
    unit = Column(String(20), default="pcs")
    wholesale_price = Column(MONEY, default=0)
    dealer_price = Column(MONEY, default=0)
    selling_price = Column(MONEY, default=0)
    cost_price = Column(MONEY, default=0)
    hsn_code = Column(String(20), nullable=True)
    gst_rate = Column(MONEY, default=0)
    low_stock_threshold = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class StockMovement(Base):
    """Append-only ledger of every stock change. item.quantity is a fast
    running total; this table is the historical source of truth it must
    always reconcile with."""
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory.id"), nullable=False, index=True)
    movement_type = Column(String(20), nullable=False)
    # OPENING_STOCK | PURCHASE | PURCHASE_CANCEL | SALE | SALE_CANCEL | ADJUSTMENT
    quantity_change = Column(Integer, nullable=False)   # signed: + increases stock, - decreases
    quantity_before = Column(Integer, nullable=False)
    quantity_after = Column(Integer, nullable=False)
    reference_type = Column(String(20), nullable=True)  # bill | purchase | item_create | item_edit
    reference_id = Column(Integer, nullable=True)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
