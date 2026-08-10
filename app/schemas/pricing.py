from pydantic import BaseModel
from typing import Optional


class PricingBase(BaseModel):
    service_name: str
    country_id: int
    currency: str
    amount: float
    billing_type: str = "ONE_TIME"
    tax_percent: float = 0.0
    discount_percent: float = 0.0


class PricingCreate(PricingBase):
    pass


class PricingResponse(PricingBase):
    id: int
    active: bool

    class Config:
        from_attributes = True
