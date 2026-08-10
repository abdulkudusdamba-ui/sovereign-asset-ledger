from app.providers.sandbox_provider import SandboxPaymentProvider


class PaymentProviderFactory:

    @staticmethod
    def get_provider(provider_name: str):

        provider_name = provider_name.lower()

        if provider_name == "sandbox":
            return SandboxPaymentProvider()

        raise ValueError(
            f"Unsupported payment provider: {provider_name}"
        )
