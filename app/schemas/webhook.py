from pydantic import BaseModel
from typing import Optional


class WebhookPaymentRequest(BaseModel):
    provider: str
    event_type: str
    transaction_id: Optional[str] = None
    status: Optional[str] = None
    payload: dict


class WebhookResponse(BaseModel):
    id: int
    provider: str
    event_type: str
    transaction_id: Optional[str] = None
    status: str

    class Config:
        from_attributes = True
