import hashlib
import hmac
import json
import os


from app.providers.payment_provider import PaymentProvider


class SandboxPaymentProvider(PaymentProvider):

    PROVIDER_NAME = "sandbox"

    def initialize_payment(self, payment):
        return {
            "success": True,
            "provider": "SAL Sandbox",
            "transaction_id": payment.transaction_id,
            "status": "PENDING",
            "provider_reference": None,
        }

    def verify_payment(self, transaction_id: str):
        return {
            "success": True,
            "provider": "SAL Sandbox",
            "transaction_id": transaction_id,
            "status": "PAID",
            "provider_reference": f"SANDBOX-{transaction_id}",
        }

    def refund_payment(self, transaction_id: str):
        return {
            "success": True,
            "provider": "SAL Sandbox",
            "transaction_id": transaction_id,
            "status": "REFUNDED",
            "provider_reference": f"SANDBOX-{transaction_id}",
        }

    @staticmethod
    def build_webhook_message(
        *,
        provider: str,
        event_type: str,
        transaction_id: str | None,
        status: str | None,
        payload: dict,
        timestamp: str,
    ) -> str:
        """
        Build the canonical message used for HMAC signing.

        Every security-relevant webhook field is included.
        """

        canonical_data = {
            "event_type": (
                event_type.strip().upper()
                if event_type is not None
                else None
            ),
            "payload": payload,
            "provider": (
                provider.strip().lower()
                if provider is not None
                else None
            ),
            "status": (
                status.strip().upper()
                if status is not None
                else None
            ),
            "timestamp": str(timestamp),
            "transaction_id": transaction_id,
        }

        return json.dumps(
            canonical_data,
            sort_keys=True,
            separators=(",", ":"),
        )

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
        Verify SAL Sandbox webhook using HMAC-SHA256.

        The signature covers:

            provider
            event_type
            transaction_id
            status
            payload
            timestamp

        Secret:

            SAL_SANDBOX_WEBHOOK_SECRET
        """

        secret = os.getenv(
            "SAL_SANDBOX_WEBHOOK_SECRET"
        )

        if not secret:
            return False

        if not signature:
            return False

        if not timestamp:
            return False

        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            return False

        if timestamp_value <= 0:
            return False

        message = self.build_webhook_message(
            provider=provider,
            event_type=event_type,
            transaction_id=transaction_id,
            status=status,
            payload=payload,
            timestamp=timestamp,
        )

        expected_signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(
            expected_signature,
            signature.strip().lower(),
        )
