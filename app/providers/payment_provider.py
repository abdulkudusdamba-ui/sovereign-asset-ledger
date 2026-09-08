from abc import ABC, abstractmethod


class PaymentProvider(ABC):

    @abstractmethod
    def initialize_payment(self, payment):
        pass

    @abstractmethod
    def verify_payment(self, transaction_id: str):
        pass

    @abstractmethod
    def refund_payment(self, transaction_id: str):
        pass

    def verify_webhook(
        self,
        *,
        provider: str,
        event_type: str,
        transaction_id: str | None,
        status: str | None,
        payload: dict,
        signature: str,
        timestamp: str,
    ) -> bool:
        """
        Verify the authenticity of a payment webhook.

        Providers with real webhook-signing mechanisms must
        override this method.

        Secure-by-default behavior:
        reject the webhook.
        """
        return False
