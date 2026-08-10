from datetime import datetime
from sqlalchemy.orm import Session

from app.models.receipt import Receipt


class ReceiptService:

    @staticmethod
    def generate_receipt_number(db: Session):

        year = datetime.utcnow().year

        count = (
            db.query(Receipt)
            .count()
        ) + 1

        return f"SAL-RCP-{year}-{count:06d}"
