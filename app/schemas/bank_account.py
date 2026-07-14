from pydantic import BaseModel

class BankAccountBase(BaseModel):
    owner: str
    bank_name: str
    account_number: str
    account_type: str
    currency: str
    balance: float


class BankAccountCreate(BankAccountBase):
    pass


class BankAccountResponse(BankAccountBase):
    id: int
    status: str

    class Config:
        from_attributes = True