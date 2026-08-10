from pydantic import BaseModel
from datetime import datetime


class ReceiptResponse(BaseModel):
    id: int
    payment_id: int
    receipt_number: str
    customer: str
    currency: str
    amount: float
    issued_at: datetime

    class Config:
        from_attributes = True
