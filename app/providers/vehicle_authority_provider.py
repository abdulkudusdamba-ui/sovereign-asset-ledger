"""
Vehicle authority provider interface and a deterministic FAKE provider.

The fake provider performs no network calls and is NOT connected to
DVLA or any other real authority. Its results prove nothing about a
real vehicle.
"""

from dataclasses import dataclass
from typing import Protocol


class ProviderUnavailableError(Exception):
    """Transient provider failure; the lookup may be retried."""


class ProviderPermanentError(Exception):
    """Non-retryable provider failure."""


@dataclass(frozen=True)
class VehicleAuthorityRecord:
    """Identity fields only. Never includes owner information."""

    vin: str | None
    registration_number: str | None
    chassis_number: str | None
    engine_number: str | None


class VehicleAuthorityProvider(Protocol):
    name: str

    def lookup(
        self,
        *,
        vin: str,
        registration_number: str,
        chassis_number: str | None = None,
        engine_number: str | None = None,
    ) -> VehicleAuthorityRecord | None:
        ...


class FakeVehicleAuthorityProvider:
    """
    Deterministic FAKE provider for development and tests.

    Default behaviour, keyed on the VIN supplied:
    - VIN ending "-FAKE-UNAVAILABLE": raises ProviderUnavailableError.
    - VIN ending "-FAKE-PERMANENT": raises ProviderPermanentError.
    - VIN ending "-FAKE-NOTFOUND": returns no record.
    - VIN ending "-FAKE-MISMATCH": returns a record with a different
      chassis number.
    - anything else: returns a record echoing the identifiers it was
      given (these are not real authority data).

    Tests may pass explicit ``records`` (keyed by VIN) or ``errors``
    (a list of exceptions raised on successive calls).
    """

    name = "FAKE"

    def __init__(
        self,
        records: dict[str, VehicleAuthorityRecord | None] | None = None,
        errors: list[Exception] | None = None,
    ):
        self.records = records
        self.errors = list(errors or [])
        self.calls = 0

    def lookup(self, *, vin, registration_number, chassis_number=None, engine_number=None):
        self.calls += 1

        if self.errors:
            raise self.errors.pop(0)

        if self.records is not None:
            return self.records.get(vin)

        if vin.endswith("-FAKE-UNAVAILABLE"):
            raise ProviderUnavailableError("fake provider unavailable")
        if vin.endswith("-FAKE-PERMANENT"):
            raise ProviderPermanentError("fake provider permanent error")
        if vin.endswith("-FAKE-NOTFOUND"):
            return None

        mismatch = vin.endswith("-FAKE-MISMATCH")
        return VehicleAuthorityRecord(
            vin=vin,
            registration_number=registration_number,
            chassis_number=(
                "FAKE-DIFFERENT-CHASSIS" if mismatch else chassis_number
            ),
            engine_number=engine_number,
        )


def get_vehicle_authority_provider(
    provider_name: str = "fake",
) -> VehicleAuthorityProvider:
    """Only the fake provider exists. No live provider is supported."""
    if provider_name.lower() == "fake":
        return FakeVehicleAuthorityProvider()

    raise ValueError(
        f"Unsupported vehicle authority provider: {provider_name}"
    )
