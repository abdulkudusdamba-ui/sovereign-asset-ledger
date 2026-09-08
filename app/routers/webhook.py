import time

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.database.database import get_db

from app.providers.provider_factory import (
    PaymentProviderFactory,
)

from app.schemas.webhook import (
    WebhookPaymentRequest,
    WebhookResponse,
)

from app.services.webhook_service import (
    WebhookService,
)


router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)


WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


@router.post(
    "/payment",
    response_model=WebhookResponse,
)
def payment_webhook(
    request: WebhookPaymentRequest,
    x_webhook_signature: str = Header(
        ...,
        alias="X-Webhook-Signature",
    ),
    x_webhook_timestamp: str = Header(
        ...,
        alias="X-Webhook-Timestamp",
    ),
    db: Session = Depends(get_db),
):
    """
    Receive an authenticated payment-provider webhook.

    Security checks happen before the financial workflow:

    1. Provider must be supported.
    2. Timestamp must be valid.
    3. Timestamp must be recent.
    4. HMAC signature must be valid.
    5. Webhook service validates provider/payment ownership.
    """

    provider_name = request.provider.strip().lower()

    try:
        provider = PaymentProviderFactory.get_provider(
            provider_name
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # ---------------------------------------------------------
    # Timestamp validation
    # ---------------------------------------------------------

    try:
        webhook_timestamp = int(
            x_webhook_timestamp.strip()
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook timestamp",
        )

    now = int(time.time())

    if abs(now - webhook_timestamp) > (
        WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
    ):
        raise HTTPException(
            status_code=401,
            detail="Webhook timestamp is expired or invalid",
        )

    # ---------------------------------------------------------
    # Signature validation
    # ---------------------------------------------------------

    authenticated = provider.verify_webhook(
        provider=provider_name,
        event_type=request.event_type,
        transaction_id=request.transaction_id,
        status=request.status,
        payload=request.payload,
        signature=x_webhook_signature,
        timestamp=x_webhook_timestamp,
    )

    if not authenticated:
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    # ---------------------------------------------------------
    # Financial webhook processing
    # ---------------------------------------------------------

    try:
        return WebhookService.process_payment_webhook(
            db=db,
            provider=provider_name,
            event_type=request.event_type,
            transaction_id=request.transaction_id,
            status=request.status,
            payload=request.payload,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to process payment webhook",
        )
