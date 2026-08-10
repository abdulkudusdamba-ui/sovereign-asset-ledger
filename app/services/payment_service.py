from datetime import datetime


class PaymentService:

    @staticmethod
    def generate_transaction_id():

        year = datetime.utcnow().year

        timestamp = int(datetime.utcnow().timestamp())

        return f"SAL-PAY-{year}-{timestamp}"
