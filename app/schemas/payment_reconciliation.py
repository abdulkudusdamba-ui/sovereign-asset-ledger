from datetime import datetime

from pydantic import BaseModel
from typing import Optional


class PaymentReconciliationResponse(BaseModel):

    id: int
    payment_id: int
    invoice_id: int

    expected_amount: float
    actual_amount: float
    currency: str
    difference: float

    status: str

    provider_reference: Optional[str] = None
    notes: Optional[str] = None

    created_at: Optional[datetime] = None
    reconciled_at: Optional[datetime] = None

    class Config:
        from_attributes = True
