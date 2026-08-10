from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InvoiceCreate(BaseModel):
    customer: str
    service: str
    currency: str = "GHS"
    subtotal: float
    tax: float = 0
    discount: float = 0
    due_date: Optional[datetime] = None


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    customer: str
    service: str
    currency: str
    subtotal: float
    tax: float
    discount: float
    total: float
    status: str
    due_date: Optional[datetime]
    paid_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
