from pydantic import BaseModel


class CryptoWalletCreate(BaseModel):
    owner: str
    wallet_name: str
    blockchain: str
    wallet_address: str
    cryptocurrency: str
    balance: float
    estimated_value: float


class CryptoWalletResponse(CryptoWalletCreate):
    id: int
    status: str

    class Config:
        from_attributes = True