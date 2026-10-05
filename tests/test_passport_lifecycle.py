from app.models.user import User
from app.core.security import hash_password


def create_admin_and_login(client, test_db):
    password = "SAL-Test-Lifecycle-2026"

    admin = User(
        full_name="SAL Lifecycle Test Administrator",
        email="lifecycle-admin@sal.test",
        password=hash_password(password),
        role="admin",
    )

    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)

    response = client.post(
        "/users/login",
        data={
            "username": admin.email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_registry_and_passport(client, headers):
    registry_response = client.post(
        "/registry/",
        json={
            "asset_type": "Land",
            "registry_id": 910001,
            "owner": "SAL Lifecycle Test Owner",
            "estimated_value": 500000,
            "status": "Active",
        },
        headers=headers,
    )

    assert registry_response.status_code == 200

    sal_id = registry_response.json()["sal_id"]

    passport_response = client.post(
        f"/passport/{sal_id}",
        headers=headers,
    )

    assert passport_response.status_code == 201

    return passport_response.json()


def test_passport_registered_to_active(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    response = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Initial activation",
            "reference": "LIFECYCLE-TEST-001",
        },
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["lifecycle_state"] == "ACTIVE"
    assert data["version"] == 2


def test_stale_version_is_rejected(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    first = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Initial activation",
            "reference": "LIFECYCLE-TEST-002",
        },
        headers=headers,
    )

    assert first.status_code == 200

    stale = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "SUSPENDED",
            "expected_version": 1,
            "reason": "Stale update",
            "reference": "LIFECYCLE-TEST-003",
        },
        headers=headers,
    )

    assert stale.status_code == 409
    assert "modified" in stale.json()["detail"].lower()

    current = client.get(
        f"/passport/{passport['sal_id']}",
        headers=headers,
    )

    assert current.status_code == 200
    assert current.json()["lifecycle_state"] == "ACTIVE"
    assert current.json()["version"] == 2


def test_invalid_transition_is_rejected(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    response = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "TRANSFERRED",
            "expected_version": 1,
            "reason": "Invalid transition",
            "reference": "LIFECYCLE-TEST-004",
        },
        headers=headers,
    )

    assert response.status_code == 409
    assert "invalid" in response.json()["detail"].lower()


def test_duplicate_lifecycle_reference_is_rejected(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    first = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Initial activation",
            "reference": "LIFECYCLE-TEST-005",
        },
        headers=headers,
    )

    assert first.status_code == 200

    second = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "TRANSFER_PENDING",
            "expected_version": 2,
            "reason": "Transfer initiation",
            "reference": "LIFECYCLE-TEST-005",
        },
        headers=headers,
    )

    assert second.status_code == 409
    assert "reference already exists" in second.json()["detail"].lower()


def test_lifecycle_history_is_recorded(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    transition = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Initial activation",
            "reference": "LIFECYCLE-TEST-006",
        },
        headers=headers,
    )

    assert transition.status_code == 200

    history = client.get(
        f"/passport/{passport['id']}/history",
        headers=headers,
    )

    assert history.status_code == 200

    records = history.json()

    assert len(records) == 1
    assert records[0]["from_state"] == "REGISTERED"
    assert records[0]["to_state"] == "ACTIVE"
    assert records[0]["reason"] == "Initial activation"
    assert records[0]["reference"] == "LIFECYCLE-TEST-006"
    assert records[0]["changed_by"] == "lifecycle-admin@sal.test"


def test_unauthenticated_lifecycle_update_is_rejected(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    response = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Unauthorized attempt",
            "reference": "LIFECYCLE-TEST-007",
        },
    )

    assert response.status_code == 401


def test_passport_lifecycle_creates_audit_event(client, test_db):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    response = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Start Passport audit integration test",
            "reference": "LIFECYCLE-AUDIT-EVENT-001",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    from app.models.audit_event import AuditEvent

    audit_event = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "ASSET_PASSPORT",
            AuditEvent.entity_id == passport["passport_id"],
            AuditEvent.reference == "LIFECYCLE-AUDIT-EVENT-001",
        )
        .first()
    )

    assert audit_event is not None
    assert audit_event.action == "PASSPORT_LIFECYCLE"
    assert audit_event.actor_type == "USER"
    assert audit_event.source == "API"
    assert audit_event.result == "SUCCESS"
    assert audit_event.asset_registry_id == passport["asset_registry_id"]
    assert audit_event.passport_id == passport["id"]
    assert audit_event.before_data is not None
    assert audit_event.after_data is not None
    assert audit_event.audit_metadata is not None


def test_passport_lifecycle_audit_event_records_authenticated_actor(
    client,
    test_db,
):
    headers = create_admin_and_login(client, test_db)
    passport = create_registry_and_passport(client, headers)

    from app.models.user import User

    user = (
        test_db.query(User)
        .filter(User.email == "lifecycle-admin@sal.test")
        .first()
    )

    assert user is not None

    response = client.patch(
        f"/passport/{passport['id']}/lifecycle",
        json={
            "lifecycle_state": "ACTIVE",
            "expected_version": 1,
            "reason": "Verify Passport lifecycle audit actor",
            "reference": "LIFECYCLE-AUDIT-ACTOR-001",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    from app.models.audit_event import AuditEvent

    audit_event = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "ASSET_PASSPORT",
            AuditEvent.entity_id == passport["passport_id"],
            AuditEvent.reference == "LIFECYCLE-AUDIT-ACTOR-001",
        )
        .first()
    )

    assert audit_event is not None
    assert audit_event.actor_id == user.id
    assert audit_event.actor_type == "USER"
    assert audit_event.source == "API"
