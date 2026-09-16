from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PurchaseBill(Base):
    __tablename__ = "purchase_bills"

    id = Column(Integer, primary_key=True, index=True)
    purchase_number = Column(String(20), unique=True, nullable=False, index=True)
    supplier_name = Column(String(100), nullable=False)
    supplier_invoice = Column(String(50), nullable=True)   # supplier's own ref number
    status = Column(String(20), default="received")        # received | cancelled
    total_amount = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("PurchaseBillItem", back_populates="bill", cascade="all, delete-orphan")


class PurchaseBillItem(Base):
    __tablename__ = "purchase_bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("purchase_bills.id"), nullable=False)
    item_id = Column(Integer, nullable=True)
    item_name = Column(String(100), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_cost = Column(Float, nullable=False)
    line_total = Column(Float, nullable=False)

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
    status = Column(String(20), default="paid")  # paid | cancelled
    customer_type = Column(String(20), default="retailer")  # wholesaler | dealer | retailer
    taxable_amount = Column(Float, default=0.0)
    igst_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("BillItem", back_populates="bill", cascade="all, delete-orphan")


class BillItem(Base):
    __tablename__ = "bill_items"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    item_id = Column(Integer, nullable=True)   # snapshot; item may be deleted later
    item_name = Column(String(100), nullable=False)
    hsn_code = Column(String(20), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    gst_rate = Column(Float, default=0.0)
    taxable_amount = Column(Float, nullable=False)
    igst_amount = Column(Float, default=0.0)
    line_total = Column(Float, nullable=False)

    bill = relationship("Bill", back_populates="items")


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
    wholesale_price = Column(Float, default=0.0)
    dealer_price = Column(Float, default=0.0)
    selling_price = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    hsn_code = Column(String(20), nullable=True)
    gst_rate = Column(Float, default=0.0)
    low_stock_threshold = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
