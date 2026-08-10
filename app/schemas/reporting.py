from pydantic import BaseModel


class FinancialSummaryResponse(BaseModel):
    total_payments: int
    total_payment_amount: float
    total_invoices: int
    paid_invoices: int
    outstanding_invoices: int
    matched_reconciliations: int
    underpaid_reconciliations: int
    overpaid_reconciliations: int
    ledger_entries: int
    ledger_credits: float


class PaymentSummaryResponse(BaseModel):
    paid: int
    pending: int
    failed: int
    refunded: int
