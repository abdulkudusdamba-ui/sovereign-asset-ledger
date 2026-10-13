from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from app.core.config import settings


@dataclass(frozen=True)
class AnchorReceipt:
    provider: str
    network_id: str
    reference: str


class BlockchainProvider(Protocol):
    provider_name: str
    network_id: str

    def anchor(self, commitment_hash: str) -> AnchorReceipt:
        """Submit a commitment and return only after provider confirmation."""

    def verify(self, commitment_hash: str, reference: str) -> bool:
        """Check that a provider reference corresponds to a commitment."""


class MockLedgerProvider:
    """Deterministic local-only ledger simulator; it does not contact a chain."""

    provider_name = "mock-ledger"
    network_id = "sal-mocknet-v1"

    def anchor(self, commitment_hash: str) -> AnchorReceipt:
        reference_hash = sha256(
            f"{self.network_id}:{commitment_hash}".encode("ascii")
        ).hexdigest()
        return AnchorReceipt(
            provider=self.provider_name,
            network_id=self.network_id,
            reference=f"mock:{reference_hash}",
        )

    def verify(self, commitment_hash: str, reference: str) -> bool:
        try:
            expected = self.anchor(commitment_hash).reference
        except (TypeError, ValueError):
            return False
        return reference == expected


def get_blockchain_provider() -> BlockchainProvider:
    if settings.SAL_BLOCKCHAIN_PROVIDER == "mock":
        return MockLedgerProvider()
    raise ValueError("Configured blockchain provider is not implemented")
