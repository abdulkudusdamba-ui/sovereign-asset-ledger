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
