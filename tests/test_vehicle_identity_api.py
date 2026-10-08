from app.core.security import hash_password
from app.models.asset_external_identifier import AssetExternalIdentifier
from app.models.asset_registry import AssetRegistry
from app.models.government_verification import GovernmentVerification
from app.models.user import User
from app.models.vehicle import Vehicle


def create_user_and_login(
    client,
    test_db,
    *,
    email,
    role,
    password,
):
    user = User(
        full_name=f"SAL Vehicle Identity {role.title()}",
        email=email,
        password=hash_password(password),
        role=role,
    )

    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    response = client.post(
        "/users/login",
        data={
            "username": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_vehicle_identity(test_db):
    vehicle = Vehicle(
        owner="SAL Vehicle Identity API Owner",
        registration_number="GT-API-ID-001",
        vin="SALVINAPIIDENTITY0001",
        chassis_number="CHASSISAPIIDENTITY0001",
        manufacturer="Mercedes-Benz",
        model="G-Class",
        year=2026,
        engine_number="ENGINEAPIIDENTITY0001",
        color="Black",
        estimated_value=250000.0,
        status="ACTIVE",
    )

    test_db.add(vehicle)
    test_db.flush()

    asset = AssetRegistry(
        sal_id="SAL-VEHICLE-API-ID-001",
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


def test_admin_can_read_vehicle_identity(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-identity-admin@sal.test",
        role="admin",
        password="SAL-Vehicle-Identity-Admin-2026",
    )

    vehicle, asset = create_vehicle_identity(test_db)

    identifier = AssetExternalIdentifier(
        asset_registry_id=asset.id,
        authority="DVLA",
        identifier_type="RFID",
        identifier_value="RFID-API-ID-001",
        status="ACTIVE",
        source_reference="DVLA-API-REF-001",
    )

    verification = GovernmentVerification(
        asset_registry_id=asset.id,
        authority="DVLA",
        reference_number="DVLA-API-VERIFY-001",
        status="VERIFIED",
        verified_by="government@sal.test",
        notes="Vehicle identity verified",
    )

    test_db.add(identifier)
    test_db.add(verification)
    test_db.commit()

    response = client.get(
        f"/vehicle-identity/{asset.sal_id}",
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sal_id"] == asset.sal_id
    assert data["asset_registry_id"] == asset.id
    assert data["vehicle_id"] == vehicle.id

    assert data["identity"]["vin"] == vehicle.vin
    assert (
        data["identity"]["chassis_number"]
        == vehicle.chassis_number
    )
    assert (
        data["identity"]["engine_number"]
        == vehicle.engine_number
    )
    assert (
        data["identity"]["registration_number"]
        == vehicle.registration_number
    )

    assert data["vehicle"]["manufacturer"] == "Mercedes-Benz"
    assert data["vehicle"]["model"] == "G-Class"
    assert data["vehicle"]["year"] == 2026

    assert len(data["external_identifiers"]) == 1
    assert (
        data["external_identifiers"][0]["identifier_value"]
        == "RFID-API-ID-001"
    )

    assert data["government_verification"]["status"] == "VERIFIED"
    assert (
        data["government_verification"]["reference_number"]
        == "DVLA-API-VERIFY-001"
    )


def test_government_can_read_vehicle_identity(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-identity-government@sal.test",
        role="government",
        password="SAL-Vehicle-Identity-Government-2026",
    )

    _, asset = create_vehicle_identity(test_db)

    response = client.get(
        f"/vehicle-identity/{asset.sal_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["sal_id"] == asset.sal_id


def test_registrar_can_read_vehicle_identity(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-identity-registrar@sal.test",
        role="registrar",
        password="SAL-Vehicle-Identity-Registrar-2026",
    )

    _, asset = create_vehicle_identity(test_db)

    response = client.get(
        f"/vehicle-identity/{asset.sal_id}",
        headers=headers,
    )

    assert response.status_code == 200


def test_viewer_cannot_read_vehicle_identity(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-identity-viewer@sal.test",
        role="viewer",
        password="SAL-Vehicle-Identity-Viewer-2026",
    )

    _, asset = create_vehicle_identity(test_db)

    response = client.get(
        f"/vehicle-identity/{asset.sal_id}",
        headers=headers,
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_read_vehicle_identity(
    client,
    test_db,
):
    _, asset = create_vehicle_identity(test_db)

    response = client.get(
        f"/vehicle-identity/{asset.sal_id}",
    )

    assert response.status_code == 401


def test_unknown_vehicle_identity_returns_not_found(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-identity-missing@sal.test",
        role="admin",
        password="SAL-Vehicle-Identity-Missing-2026",
    )

    response = client.get(
        "/vehicle-identity/SAL-DOES-NOT-EXIST",
        headers=headers,
    )

    assert response.status_code == 404
