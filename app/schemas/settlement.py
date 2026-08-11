from pydantic import BaseModel
from typing import Optional


class SettlementResponse(BaseModel):
    payment_id: int
    status: str
    settled: bool
    reason: str

    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    ledger_entry_id: Optional[int] = None
    reconciliation_id: Optional[int] = None
