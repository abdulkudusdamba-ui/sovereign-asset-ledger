from app.core.security import hash_password
from app.models.asset_registry import AssetRegistry
from app.models.audit_event import AuditEvent
from app.models.user import User


def create_user_and_login(
    client,
    test_db,
    *,
    email,
    role,
    password,
):
    user = User(
        full_name=f"SAL External ID {role.title()}",
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


def create_asset(test_db, *, registry_id=1, sal_id="SAL-EXT-001"):
    asset = AssetRegistry(
        sal_id=sal_id,
        asset_type="Vehicle",
        registry_id=registry_id,
        owner="SAL Test Owner",
        estimated_value=100000,
        status="Active",
        sal_verification="VERIFIED",
        government_verification="NOT_VERIFIED",
    )

    test_db.add(asset)
    test_db.commit()
    test_db.refresh(asset)

    return asset


def test_admin_can_create_external_identifier(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-create@sal.test",
        role="admin",
        password="SAL-External-Admin-Create-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=101,
        sal_id="SAL-EXT-CREATE-001",
    )

    response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "dvla",
            "identifier_type": "rfid",
            "identifier_value": "rfid-001",
            "source_reference": "DVLA-REF-001",
        },
        headers=headers,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["asset_registry_id"] == asset.id
    assert data["authority"] == "DVLA"
    assert data["identifier_type"] == "RFID"
    assert data["identifier_value"] == "RFID-001"
    assert data["status"] == "ACTIVE"


def test_registrar_can_create_external_identifier(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-registrar-create@sal.test",
        role="registrar",
        password="SAL-External-Registrar-Create-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=102,
        sal_id="SAL-EXT-CREATE-002",
    )

    response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-002",
        },
        headers=headers,
    )

    assert response.status_code == 201


def test_viewer_cannot_create_external_identifier(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-viewer-create@sal.test",
        role="viewer",
        password="SAL-External-Viewer-Create-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=103,
        sal_id="SAL-EXT-CREATE-003",
    )

    response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-003",
        },
        headers=headers,
    )

    assert response.status_code == 403


def test_unauthenticated_cannot_create_external_identifier(
    client,
    test_db,
):
    asset = create_asset(
        test_db,
        registry_id=104,
        sal_id="SAL-EXT-CREATE-004",
    )

    response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-004",
        },
    )

    assert response.status_code == 401


def test_duplicate_active_external_identifier_returns_conflict(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-duplicate@sal.test",
        role="admin",
        password="SAL-External-Admin-Duplicate-2026",
    )

    asset_one = create_asset(
        test_db,
        registry_id=105,
        sal_id="SAL-EXT-DUP-001",
    )

    asset_two = create_asset(
        test_db,
        registry_id=106,
        sal_id="SAL-EXT-DUP-002",
    )

    payload = {
        "authority": "DVLA",
        "identifier_type": "RFID",
        "identifier_value": "RFID-DUP-001",
    }

    first = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset_one.id,
            **payload,
        },
        headers=headers,
    )

    assert first.status_code == 201

    second = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset_two.id,
            **payload,
        },
        headers=headers,
    )

    assert second.status_code == 409


def test_missing_asset_returns_not_found(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-missing-asset@sal.test",
        role="admin",
        password="SAL-External-Admin-Missing-2026",
    )

    response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": 999999,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-MISSING-ASSET",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_admin_can_list_asset_external_identifiers(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-list@sal.test",
        role="admin",
        password="SAL-External-Admin-List-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=107,
        sal_id="SAL-EXT-LIST-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-LIST-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/asset-external-identifiers/asset/{asset.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["identifier_value"] == "RFID-LIST-001"


def test_government_can_read_external_identifiers(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-government-read@sal.test",
        role="government",
        password="SAL-External-Government-Read-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=108,
        sal_id="SAL-EXT-GOV-001",
    )

    admin_headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-gov-setup@sal.test",
        role="admin",
        password="SAL-External-Admin-Gov-2026",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-GOV-001",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        f"/asset-external-identifiers/asset/{asset.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()[0]["identifier_value"] == "RFID-GOV-001"


def test_viewer_cannot_read_external_identifiers(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-viewer-read@sal.test",
        role="viewer",
        password="SAL-External-Viewer-Read-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=109,
        sal_id="SAL-EXT-VIEW-001",
    )

    response = client.get(
        f"/asset-external-identifiers/asset/{asset.id}",
        headers=headers,
    )

    assert response.status_code == 403


def test_lookup_by_external_identifier(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-lookup@sal.test",
        role="admin",
        password="SAL-External-Admin-Lookup-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=110,
        sal_id="SAL-EXT-LOOKUP-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-LOOKUP-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    response = client.get(
        "/asset-external-identifiers/lookup/by-external-id",
        params={
            "authority": "dvla",
            "identifier_type": "rfid",
            "identifier_value": "rfid-lookup-001",
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["sal_id"] == "SAL-EXT-LOOKUP-001"
    assert data["asset_registry_id"] == asset.id
    assert data["asset_type"] == "Vehicle"
    assert data["identifier"]["authority"] == "DVLA"
    assert data["identifier"]["identifier_type"] == "RFID"
    assert data["identifier"]["identifier_value"] == "RFID-LOOKUP-001"


def test_unknown_external_identifier_returns_not_found(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-lookup-missing@sal.test",
        role="admin",
        password="SAL-External-Admin-Lookup-Missing-2026",
    )

    response = client.get(
        "/asset-external-identifiers/lookup/by-external-id",
        params={
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "DOES-NOT-EXIST",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_admin_can_get_one_external_identifier(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-get-one@sal.test",
        role="admin",
        password="SAL-External-Admin-Get-One-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=111,
        sal_id="SAL-EXT-GET-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-GET-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    identifier_id = create_response.json()["id"]

    response = client.get(
        f"/asset-external-identifiers/{identifier_id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == identifier_id


def test_admin_can_change_external_identifier_status(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-status@sal.test",
        role="admin",
        password="SAL-External-Admin-Status-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=112,
        sal_id="SAL-EXT-STATUS-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-STATUS-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    identifier_id = create_response.json()["id"]

    response = client.patch(
        f"/asset-external-identifiers/{identifier_id}/status",
        json={
            "status": "REVOKED",
            "reason": "Test revocation",
            "reference": "TEST-REV-001",
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "REVOKED"


def test_viewer_cannot_change_external_identifier_status(
    client,
    test_db,
):
    admin_headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-status-viewer-setup@sal.test",
        role="admin",
        password="SAL-External-Admin-Status-Setup-2026",
    )

    viewer_headers = create_user_and_login(
        client,
        test_db,
        email="external-viewer-status@sal.test",
        role="viewer",
        password="SAL-External-Viewer-Status-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=113,
        sal_id="SAL-EXT-STATUS-002",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-STATUS-002",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201

    identifier_id = create_response.json()["id"]

    response = client.patch(
        f"/asset-external-identifiers/{identifier_id}/status",
        json={"status": "REVOKED"},
        headers=viewer_headers,
    )

    assert response.status_code == 403


def test_status_change_creates_audit_event(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-audit-api@sal.test",
        role="admin",
        password="SAL-External-Admin-Audit-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=114,
        sal_id="SAL-EXT-AUDIT-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-AUDIT-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    identifier_id = create_response.json()["id"]

    status_response = client.patch(
        f"/asset-external-identifiers/{identifier_id}/status",
        json={
            "status": "REVOKED",
            "reason": "Audit API test",
            "reference": "AUDIT-API-001",
        },
        headers=headers,
    )

    assert status_response.status_code == 200

    events = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.action
            == "EXTERNAL_IDENTIFIER_STATUS_CHANGED",
            AuditEvent.entity_id == str(identifier_id),
        )
        .all()
    )

    assert len(events) == 1
    assert events[0].result == "SUCCESS"


def test_active_lookup_stops_after_identifier_is_revoked(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="external-admin-revoked-lookup@sal.test",
        role="admin",
        password="SAL-External-Admin-Revoked-2026",
    )

    asset = create_asset(
        test_db,
        registry_id=115,
        sal_id="SAL-EXT-REVOKED-001",
    )

    create_response = client.post(
        "/asset-external-identifiers",
        json={
            "asset_registry_id": asset.id,
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-REVOKED-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201

    identifier_id = create_response.json()["id"]

    revoke_response = client.patch(
        f"/asset-external-identifiers/{identifier_id}/status",
        json={"status": "REVOKED"},
        headers=headers,
    )

    assert revoke_response.status_code == 200

    lookup_response = client.get(
        "/asset-external-identifiers/lookup/by-external-id",
        params={
            "authority": "DVLA",
            "identifier_type": "RFID",
            "identifier_value": "RFID-REVOKED-001",
        },
        headers=headers,
    )

    assert lookup_response.status_code == 404
