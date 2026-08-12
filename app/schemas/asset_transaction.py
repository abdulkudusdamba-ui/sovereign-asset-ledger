from pydantic import BaseModel
from typing import Optional


class AssetTransactionCreate(BaseModel):
    asset_id: Optional[int] = None
    asset_type: str
    transaction_type: str
    seller: Optional[str] = None
    buyer: Optional[str] = None
    amount: float
    currency: str = "GHS"
    description: Optional[str] = None


class AssetTransactionResponse(BaseModel):
    id: int
    asset_id: Optional[int] = None
    asset_type: str
    transaction_type: str
    seller: Optional[str] = None
    buyer: Optional[str] = None
    amount: float
    currency: str
    status: str
    payment_id: Optional[int] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True
