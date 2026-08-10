from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.webhook import (
    WebhookPaymentRequest,
    WebhookResponse
)
from app.services.webhook_service import WebhookService


router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"]
)


@router.post(
    "/payment",
    response_model=WebhookResponse
)
def payment_webhook(
    request: WebhookPaymentRequest,
    db: Session = Depends(get_db)
):

    return WebhookService.process_payment_webhook(
        db=db,
        provider=request.provider,
        event_type=request.event_type,
        transaction_id=request.transaction_id,
        status=request.status,
        payload=request.payload
    )
