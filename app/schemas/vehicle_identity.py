from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VehicleIdentityFields(BaseModel):
    vin: str
    chassis_number: str | None
    engine_number: str
    registration_number: str


class VehicleIdentityVehicleDetails(BaseModel):
    manufacturer: str | None
    model: str | None
    year: int | None
    color: str | None
    status: str | None


class VehicleIdentitySalDetails(BaseModel):
    status: str | None
    verification: str


class VehicleIdentityGovernmentVerification(BaseModel):
    status: str
    authority: str | None
    reference_number: str | None
    verified_by: str | None
    verified_at: datetime | None
    notes: str | None


class VehicleIdentityExternalIdentifier(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_registry_id: int
    authority: str
    identifier_type: str
    identifier_value: str
    status: str
    source_reference: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VehicleIdentityResponse(BaseModel):
    sal_id: str
    asset_registry_id: int
    vehicle_id: int
    identity: VehicleIdentityFields
    vehicle: VehicleIdentityVehicleDetails
    sal: VehicleIdentitySalDetails
    external_identifiers: list[VehicleIdentityExternalIdentifier]
    government_verification: VehicleIdentityGovernmentVerification
