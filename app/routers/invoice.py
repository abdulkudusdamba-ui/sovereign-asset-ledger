from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.invoice import Invoice
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceResponse,
)
from app.services.invoice_service import InvoiceService

router = APIRouter(
    prefix="/invoice",
    tags=["Invoice"]
)


@router.post(
    "/",
    response_model=InvoiceResponse
)
def create_invoice(
    request: InvoiceCreate,
    db: Session = Depends(get_db)
):

    invoice = Invoice(

        invoice_number=InvoiceService.generate_invoice_number(db),

        customer=request.customer,

        service=request.service,

        currency=request.currency,

        subtotal=request.subtotal,

        tax=request.tax,

        discount=request.discount,

        total=InvoiceService.calculate_total(
            request.subtotal,
            request.tax,
            request.discount
        ),

        due_date=request.due_date,

        status="DRAFT"
    )

    db.add(invoice)

    db.commit()

    db.refresh(invoice)

    return invoice


@router.get(
    "/",
    response_model=list[InvoiceResponse]
)
def get_invoices(
    db: Session = Depends(get_db)
):

    return db.query(Invoice).all()


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse
)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db)
):

    return (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id)
        .first()
    )
