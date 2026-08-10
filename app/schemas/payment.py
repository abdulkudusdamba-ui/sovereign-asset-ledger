from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PaymentCreate(BaseModel):
    invoice_id: int
    provider: str
    payment_method: str
    currency: str = "GHS"
    amount: float


class PaymentResponse(BaseModel):
    id: int
    invoice_id: int
    transaction_id: str
    provider: str
    payment_method: str
    currency: str
    amount: float
    status: str
    provider_reference: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentStatusUpdate(BaseModel):
    status: str
    provider_reference: Optional[str] = None
