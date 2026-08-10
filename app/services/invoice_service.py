from datetime import datetime
from sqlalchemy.orm import Session

from app.models.invoice import Invoice


class InvoiceService:

    @staticmethod
    def generate_invoice_number(db: Session):

        year = datetime.utcnow().year

        count = (
            db.query(Invoice)
            .count()
        ) + 1

        return f"SAL-INV-{year}-{count:06d}"

    @staticmethod
    def calculate_total(
        subtotal: float,
        tax: float,
        discount: float
    ):

        total = subtotal + tax - discount

        if total < 0:
            total = 0

        return round(total, 2)