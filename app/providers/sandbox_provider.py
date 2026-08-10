from app.providers.payment_provider import PaymentProvider


class SandboxPaymentProvider(PaymentProvider):

    def initialize_payment(self, payment):

        return {
            "success": True,
            "provider": "SAL Sandbox",
            "transaction_id": payment.transaction_id,
            "status": "PENDING"
        }

    def verify_payment(self, transaction_id: str):

        return {
            "transaction_id": transaction_id,
            "status": "PAID"
        }

    def refund_payment(self, transaction_id: str):

        return {
            "transaction_id": transaction_id,
            "status": "REFUNDED"
        }
