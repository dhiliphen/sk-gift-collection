from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PurchaseItemCreate(BaseModel):
    item_id: int
    quantity: int = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)


class PurchaseCreate(BaseModel):
    supplier_name: str = Field(..., min_length=1, max_length=100)
    supplier_invoice: Optional[str] = None
    items: List[PurchaseItemCreate]


class PurchaseItemResponse(BaseModel):
    id: int
    item_id: Optional[int]
    item_name: str
    unit: Optional[str]
    quantity: int
    unit_cost: float
    line_total: float

    class Config:
        from_attributes = True


class PurchaseResponse(BaseModel):
    id: int
    purchase_number: str
    supplier_name: str
    supplier_invoice: Optional[str]
    status: str
    total_amount: float
    created_at: Optional[datetime]
    items: List[PurchaseItemResponse] = []

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
    unit_price: float = Field(..., ge=0)


class BillCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_phone: Optional[str] = None
    customer_type: str = Field(default="retailer", pattern="^(wholesaler|dealer|retailer)$")
    items: List[BillItemCreate]


class BillItemResponse(BaseModel):
    id: int
    item_id: Optional[int]
    item_name: str
    hsn_code: Optional[str]
    unit: Optional[str]
    quantity: int
    unit_price: float
    gst_rate: float
    taxable_amount: float
    igst_amount: float
    line_total: float

    class Config:
        from_attributes = True


class BillResponse(BaseModel):
    id: int
    invoice_number: str
    customer_name: str
    customer_phone: Optional[str]
    customer_type: str
    status: str
    taxable_amount: float
    igst_amount: float
    total_amount: float
    created_at: Optional[datetime]
    items: List[BillItemResponse] = []

    class Config:
        from_attributes = True


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
    cost_price: float = Field(default=0.0, ge=0)
    wholesale_price: float = Field(default=0.0, ge=0)
    dealer_price: float = Field(default=0.0, ge=0)
    selling_price: float = Field(default=0.0, ge=0)
    hsn_code: Optional[str] = None
    gst_rate: float = Field(default=0.0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = None
    supplier: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)
    unit: Optional[str] = None
    cost_price: Optional[float] = Field(None, ge=0)
    wholesale_price: Optional[float] = Field(None, ge=0)
    dealer_price: Optional[float] = Field(None, ge=0)
    selling_price: Optional[float] = Field(None, ge=0)
    hsn_code: Optional[str] = None
    gst_rate: Optional[float] = Field(None, ge=0)
    low_stock_threshold: Optional[int] = Field(None, ge=0)


class StockUpdate(BaseModel):
    quantity_change: int = Field(..., description="Positive to add, negative to deduct")


class ItemResponse(BaseModel):
    id: int
    name: str
    category: Optional[str]
    supplier: Optional[str]
    quantity: int
    unit: str
    cost_price: float
    wholesale_price: float
    dealer_price: float
    selling_price: float
    hsn_code: Optional[str]
    gst_rate: float
    low_stock_threshold: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
