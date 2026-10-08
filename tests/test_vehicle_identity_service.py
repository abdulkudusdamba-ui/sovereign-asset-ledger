import pytest

from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification
from app.models.vehicle import Vehicle
from app.services.vehicle_identity_service import (
    VehicleIdentityConflictError,
    VehicleIdentityNotFoundError,
    get_vehicle_identity_by_sal_id,
)


def create_vehicle_identity_fixture(test_db):
    vehicle = Vehicle(
        owner="SAL Vehicle Identity Owner",
        registration_number="GT-ID-001",
        vin="SALVINIDENTITY000001",
        chassis_number="CHASSISIDENTITY000001",
        manufacturer="Mercedes-Benz",
        model="G-Class",
        year=2026,
        engine_number="ENGINEIDENTITY000001",
        color="Black",
        estimated_value=200000.0,
        status="ACTIVE",
    )

    test_db.add(vehicle)
    test_db.flush()

    asset = AssetRegistry(
        sal_id="SAL-VEHICLE-IDENTITY-001",
        asset_type="Vehicle",
        registry_id=vehicle.id,
        owner=vehicle.owner,
        estimated_value=vehicle.estimated_value,
        status="Active",
        sal_verification="VERIFIED",
        government_verification="NOT_VERIFIED",
    )

    test_db.add(asset)
    test_db.commit()
    test_db.refresh(vehicle)
    test_db.refresh(asset)

    return vehicle, asset


def test_get_vehicle_identity_returns_intrinsic_identity(
    test_db,
):
    vehicle, asset = create_vehicle_identity_fixture(test_db)

    result = get_vehicle_identity_by_sal_id(
        test_db,
        sal_id=asset.sal_id,
    )

    assert result["sal_id"] == asset.sal_id
    assert result["asset_registry_id"] == asset.id
    assert result["vehicle_id"] == vehicle.id

    assert result["identity"]["vin"] == vehicle.vin
    assert (
        result["identity"]["chassis_number"]
        == vehicle.chassis_number
    )
    assert (
        result["identity"]["engine_number"]
        == vehicle.engine_number
    )
    assert (
        result["identity"]["registration_number"]
        == vehicle.registration_number
    )


def test_get_vehicle_identity_returns_vehicle_details(
    test_db,
):
    vehicle, asset = create_vehicle_identity_fixture(test_db)

    result = get_vehicle_identity_by_sal_id(
        test_db,
        sal_id=asset.sal_id,
    )

    assert result["vehicle"]["manufacturer"] == "Mercedes-Benz"
    assert result["vehicle"]["model"] == "G-Class"
    assert result["vehicle"]["year"] == 2026
    assert result["vehicle"]["color"] == "Black"
    assert result["vehicle"]["status"] == "ACTIVE"


def test_get_vehicle_identity_returns_active_external_identifiers(
    test_db,
):
    vehicle, asset = create_vehicle_identity_fixture(test_db)

    active_identifier = AssetExternalIdentifier(
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="DVLA-RFID-IDENTITY-001",
        status="ACTIVE",
    )

    retired_identifier = AssetExternalIdentifier(
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="REGISTRATION",
        identifier_value="GT-RETIRED-001",
        status="RETIRED",
    )

    test_db.add_all([
        active_identifier,
        retired_identifier,
    ])
    test_db.commit()

    result = get_vehicle_identity_by_sal_id(
        test_db,
        sal_id=asset.sal_id,
    )

    assert len(result["external_identifiers"]) == 1

    identifier = result["external_identifiers"][0]

    assert identifier.id == active_identifier.id
    assert identifier.authority == "DVLA"
    assert identifier.identifier_type == "RFID"
    assert identifier.identifier_value == "DVLA-RFID-IDENTITY-001"
    assert identifier.status == "ACTIVE"


def test_get_vehicle_identity_returns_latest_government_verification(
    test_db,
):
    vehicle, asset = create_vehicle_identity_fixture(test_db)

    first_verification = GovernmentVerification(
        asset_registry_id=asset.id,
        authority="DVLA",
        reference_number="DVLA-VERIFY-001",
        status="REJECTED",
        verified_by="government-old@sal.test",
        notes="Old verification result",
    )

    latest_verification = GovernmentVerification(
        asset_registry_id=asset.id,
        authority="DVLA",
        reference_number="DVLA-VERIFY-002",
        status="VERIFIED",
        verified_by="government@sal.test",
        notes="Latest verification result",
    )

    test_db.add_all([
        first_verification,
        latest_verification,
    ])
    test_db.commit()

    result = get_vehicle_identity_by_sal_id(
        test_db,
        sal_id=asset.sal_id,
    )

    verification = result["government_verification"]

    assert verification["status"] == "VERIFIED"
    assert verification["authority"] == "DVLA"
    assert (
        verification["reference_number"]
        == "DVLA-VERIFY-002"
    )
    assert verification["verified_by"] == "government@sal.test"
    assert verification["notes"] == "Latest verification result"


def test_get_vehicle_identity_defaults_to_not_verified(
    test_db,
):
    vehicle, asset = create_vehicle_identity_fixture(test_db)

    result = get_vehicle_identity_by_sal_id(
        test_db,
        sal_id=asset.sal_id,
    )

    verification = result["government_verification"]

    assert verification["status"] == "NOT_VERIFIED"
    assert verification["authority"] is None
    assert verification["reference_number"] is None
    assert verification["verified_by"] is None
    assert verification["verified_at"] is None
    assert verification["notes"] is None


def test_get_vehicle_identity_rejects_unknown_sal_id(
    test_db,
):
    with pytest.raises(VehicleIdentityNotFoundError):
        get_vehicle_identity_by_sal_id(
            test_db,
            sal_id="SAL-DOES-NOT-EXIST",
        )


def test_get_vehicle_identity_detects_missing_vehicle_record(
    test_db,
):
    asset = AssetRegistry(
        sal_id="SAL-VEHICLE-BROKEN-001",
        asset_type="Vehicle",
        registry_id=999999,
        owner="Broken Vehicle Owner",
        estimated_value=100000.0,
        status="Active",
        sal_verification="VERIFIED",
        government_verification="NOT_VERIFIED",
    )

    test_db.add(asset)
    test_db.commit()

    with pytest.raises(VehicleIdentityConflictError):
        get_vehicle_identity_by_sal_id(
            test_db,
            sal_id=asset.sal_id,
        )
