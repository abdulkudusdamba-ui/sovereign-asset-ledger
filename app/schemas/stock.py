from pydantic import BaseModel


class StockCreate(BaseModel):
    owner: str
    company_name: str
    ticker_symbol: str
    shares: float
    share_price: float
    estimated_value: float


class StockResponse(StockCreate):
    id: int
    status: str

    class Config:
        from_attributes = True