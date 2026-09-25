from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.money import Money


class PurchaseItemCreate(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)
    unit_cost: Money = Field(..., ge=0)


class PurchaseCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=100)
    supplier_invoice: Optional[str] = None
    # Set to record this receipt against an existing (CONFIRMED or
    # PARTIALLY_RECEIVED) purchase order. Leave unset for the simplified
    # direct-receipt flow — this app's original purchase behavior.
    purchase_order_id: Optional[int] = None
    items: List[PurchaseItemCreate]


class PurchaseItemResponse(BaseModel):
    id: int
    item_id: Optional[int]
    item_name: str
    unit: Optional[str]
    quantity: int
    quantity_returned: int
    unit_cost: Money
    line_total: Money

    class Config:
        from_attributes = True


class PurchaseResponse(BaseModel):
    id: int
    purchase_number: str
    supplier_name: str
    supplier_invoice: Optional[str]
    purchase_order_id: Optional[int]
    status: str
    total_amount: Money
    created_at: Optional[datetime]
    items: List[PurchaseItemResponse] = []

    class Config:
        from_attributes = True


class PurchaseOrderItemCreate(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)
    unit_cost: Money = Field(..., ge=0)


class PurchaseOrderCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=100)
    expected_delivery_date: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[PurchaseOrderItemCreate]


class PurchaseOrderItemResponse(BaseModel):
    id: int
    item_id: Optional[int]
    item_name: str
    unit: Optional[str]
    quantity_ordered: int
    quantity_received: int
    unit_cost: Money
    line_total: Money

    class Config:
        from_attributes = True


class PurchaseOrderResponse(BaseModel):
    id: int
    po_number: str
    supplier_name: str
    order_date: Optional[datetime]
    expected_delivery_date: Optional[datetime]
    status: str
    total_amount: Money
    notes: Optional[str]
    created_at: Optional[datetime]
    items: List[PurchaseOrderItemResponse] = []

    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    customer_type: str = Field(..., pattern="^(wholesaler|dealer|retailer)$")
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    customer_type: Optional[str] = Field(None, pattern="^(wholesaler|dealer|retailer)$")
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CustomerResponse(BaseModel):
    id: int
    name: str
    customer_type: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class BillItemCreate(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)
    unit_price: Money = Field(..., ge=0)


_PAYMENT_METHOD_PATTERN = "^(cash|upi|card|bank_transfer|cheque|other)$"


class BillCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_phone: Optional[str] = None
    customer_type: str = Field(default="retailer", pattern="^(wholesaler|dealer|retailer)$")
    items: List[BillItemCreate]
    # Payment collected at the time of sale. Defaults to the full invoice
    # total (the app's original cash-sale behavior) when omitted, so existing
    # callers keep working unchanged. Pass a smaller amount to record a
    # partial/credit sale.
    amount_paid: Optional[Money] = Field(default=None, ge=0)
    payment_method: str = Field(default="cash", pattern=_PAYMENT_METHOD_PATTERN)
    payment_reference: Optional[str] = None
    due_date: Optional[datetime] = None


class BillItemResponse(BaseModel):
    id: int
    item_id: Optional[int]
    item_name: str
    hsn_code: Optional[str]
    unit: Optional[str]
    quantity: int
    quantity_returned: int
    unit_price: Money
    gst_rate: Money
    taxable_amount: Money
    igst_amount: Money
    line_total: Money

    class Config:
        from_attributes = True


class BillResponse(BaseModel):
    id: int
    invoice_number: str
    customer_name: str
    customer_phone: Optional[str]
    customer_type: str
    status: str
    taxable_amount: Money
    igst_amount: Money
    total_amount: Money
    amount_paid: Money
    balance_due: Money
    payment_status: str
    due_date: Optional[datetime]
    created_at: Optional[datetime]
    items: List[BillItemResponse] = []
    warnings: List[str] = []

    class Config:
        from_attributes = True


class PaymentCreate(BaseModel):
    amount: Money = Field(..., gt=0)
    payment_method: str = Field(default="cash", pattern=_PAYMENT_METHOD_PATTERN)
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    payment_date: Optional[datetime] = None


class PaymentResponse(BaseModel):
    id: int
    bill_id: int
    amount: Money
    payment_method: str
    reference_number: Optional[str]
    notes: Optional[str]
    status: str
    payment_date: Optional[datetime]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class BillCancelResponse(BaseModel):
    """Returned by PATCH /api/bills/{id}/cancel.
    warnings is non-empty when bill line items referenced items that have since
    been deleted — those quantities could not be restored to inventory."""
    bill: BillResponse
    warnings: List[str] = []


class PurchaseCancelResponse(BaseModel):
    """Returned by PATCH /api/purchases/{id}/cancel.
    warnings is non-empty when purchase line items referenced items that have since
    been deleted — those quantities could not be deducted from inventory."""
    purchase: PurchaseResponse
    warnings: List[str] = []


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class CategoryUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class UnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)


class UnitUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)


class UnitResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SupplierResponse(BaseModel):
    id: int
    name: str
    contact_person: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = None
    supplier: Optional[str] = None
    quantity: int = Field(default=0, ge=0)
    unit: str = Field(default="pcs")
    cost_price: Money = Field(default=Decimal("0"), ge=0)
    wholesale_price: Money = Field(default=Decimal("0"), ge=0)
    dealer_price: Money = Field(default=Decimal("0"), ge=0)
    selling_price: Money = Field(default=Decimal("0"), ge=0)
    hsn_code: Optional[str] = None
    gst_rate: Money = Field(default=Decimal("0"), ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    cost_price: Optional[Money] = Field(None, ge=0)
    wholesale_price: Optional[Money] = Field(None, ge=0)
    dealer_price: Optional[Money] = Field(None, ge=0)
    selling_price: Optional[Money] = Field(None, ge=0)
    hsn_code: Optional[str] = None
    gst_rate: Optional[Money] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)


class StockUpdate(BaseModel):
    quantity_change: int = Field(..., description="Positive to add, negative to deduct")


class StockMovementResponse(BaseModel):
    id: int
    item_id: int
    movement_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reference_type: Optional[str]
    reference_id: Optional[int]
    note: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class ItemResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    supplier: Optional[str]
    quantity: int
    unit: str
    cost_price: Money
    wholesale_price: Money
    dealer_price: Money
    selling_price: Money
    hsn_code: Optional[str]
    gst_rate: Money
    low_stock_threshold: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DashboardAlert(BaseModel):
    level: str  # warning | info
    message: str


class DashboardToday(BaseModel):
    sales_amount: Money
    purchases_amount: Money
    payments_received: Money
    outstanding_amount: Money


class DashboardInventory(BaseModel):
    total_products: int
    stock_value: Money
    low_stock_count: int
    out_of_stock_count: int


class DashboardSales(BaseModel):
    invoices_today: int
    pending_payment_count: int
    recent_invoices: List[BillResponse]


class DashboardPurchases(BaseModel):
    recent_purchases: List[PurchaseResponse]


class DashboardResponse(BaseModel):
    today: DashboardToday
    inventory: DashboardInventory
    sales: DashboardSales
    purchases: DashboardPurchases
    alerts: List[DashboardAlert]


_ROLE_PATTERN = "^(ADMIN|MANAGER|SALES|PURCHASE|INVENTORY|ACCOUNTANT|VIEWER)$"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=200)
    # Defaults to the least-privileged role — ADMIN must be a deliberate choice.
    role: str = Field(default="VIEWER", pattern=_ROLE_PATTERN)


class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern=_ROLE_PATTERN)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=200)


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: int
    username: Optional[str]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    old_value: Optional[str]
    new_value: Optional[str]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class SalesReturnItemCreate(BaseModel):
    bill_item_id: int
    quantity: int = Field(..., gt=0)


class SalesReturnCreate(BaseModel):
    reason: Optional[str] = None
    items: List[SalesReturnItemCreate]


class SalesReturnItemResponse(BaseModel):
    id: int
    bill_item_id: int
    item_id: Optional[int]
    item_name: str
    quantity: int
    unit_price: Money
    gst_rate: Money
    taxable_amount: Money
    igst_amount: Money
    line_total: Money

    class Config:
        from_attributes = True


class SalesReturnResponse(BaseModel):
    id: int
    credit_note_number: str
    bill_id: int
    customer_name: str
    reason: Optional[str]
    taxable_amount: Money
    igst_amount: Money
    total_amount: Money
    status: str
    created_at: Optional[datetime]
    items: List[SalesReturnItemResponse] = []
    warnings: List[str] = []

    class Config:
        from_attributes = True


class PurchaseReturnItemCreate(BaseModel):
    purchase_item_id: int
    quantity: int = Field(..., gt=0)


class PurchaseReturnCreate(BaseModel):
    reason: Optional[str] = None
    items: List[PurchaseReturnItemCreate]


class PurchaseReturnItemResponse(BaseModel):
    id: int
    purchase_item_id: int
    item_id: Optional[int]
    item_name: str
    quantity: int
    unit_cost: Money
    line_total: Money

    class Config:
        from_attributes = True


class PurchaseReturnResponse(BaseModel):
    id: int
    debit_note_number: str
    purchase_id: int
    supplier_name: str
    reason: Optional[str]
    total_amount: Money
    status: str
    created_at: Optional[datetime]
    items: List[PurchaseReturnItemResponse] = []
    warnings: List[str] = []

    class Config:
        from_attributes = True
