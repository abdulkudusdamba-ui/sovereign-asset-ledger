from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.reporting import (
    FinancialSummaryResponse,
    PaymentSummaryResponse,
)
from app.services.reporting_service import ReportingService


router = APIRouter(
    prefix="/reports",
    tags=["Financial Reports"]
)


@router.get(
    "/financial-summary",
    response_model=FinancialSummaryResponse
)
def financial_summary(
    db: Session = Depends(get_db)
):
    return ReportingService.get_financial_summary(db)


@router.get(
    "/payment-summary",
    response_model=PaymentSummaryResponse
)
def payment_summary(
    db: Session = Depends(get_db)
):
    return ReportingService.get_payment_summary(db)
