from app.models.user import User
from app.core.security import hash_password


def create_user_and_login(client, test_db, role, email):
    password = "SAL-Test-Evidence-2026"

    user = User(
        full_name=f"Evidence {role.title()}",
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

    assert response.status_code == 200, response.text

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_registry_and_passport(client, headers):
    registry_response = client.post(
        "/registry/",
        json={
            "asset_type": "Land",
            "registry_id": 920001,
            "owner": "SAL Evidence Test Owner",
            "estimated_value": 400000,
            "status": "Active",
        },
        headers=headers,
    )

    assert registry_response.status_code == 200, registry_response.text

    sal_id = registry_response.json()["sal_id"]

    passport_response = client.post(
        f"/passport/{sal_id}",
        headers=headers,
    )

    assert passport_response.status_code == 201, passport_response.text

    return passport_response.json()


def test_admin_can_create_evidence(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-admin@sal.test",
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Ownership supporting document",
            "description": "Evidence submitted for verification review.",
            "source": "SAL Evidence Test",
            "reference": "EVIDENCE-ADMIN-001",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["passport_id"] == passport["id"]
    assert data["evidence_type"] == "DOCUMENT"
    assert data["title"] == "Ownership supporting document"
    assert data["status"] == "SUBMITTED"
    assert data["submitted_by"] == "evidence-admin@sal.test"
    assert data["evidence_id"].startswith("SAL-EVIDENCE-")


def test_registrar_can_create_evidence(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "registrar",
        "evidence-registrar@sal.test",
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "PHOTO",
            "title": "Asset verification photograph",
            "reference": "EVIDENCE-REGISTRAR-001",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text


def test_viewer_cannot_create_evidence(client, test_db):
    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-viewer-setup@sal.test",
    )

    passport = create_registry_and_passport(client, admin_headers)

    viewer_headers = create_user_and_login(
        client,
        test_db,
        "viewer",
        "evidence-viewer@sal.test",
    )

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Unauthorized evidence",
        },
        headers=viewer_headers,
    )

    assert response.status_code == 403


def test_government_cannot_create_evidence(client, test_db):
    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-government-setup@sal.test",
    )

    passport = create_registry_and_passport(client, admin_headers)

    government_headers = create_user_and_login(
        client,
        test_db,
        "government",
        "evidence-government@sal.test",
    )

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "GOVERNMENT_RECORD",
            "title": "Unauthorized government evidence",
        },
        headers=government_headers,
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_create_evidence(client, test_db):
    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-unauth-setup@sal.test",
    )

    passport = create_registry_and_passport(client, admin_headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Unauthenticated evidence",
        },
    )

    assert response.status_code == 401


def test_admin_can_list_and_retrieve_evidence(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-retrieval@sal.test",
    )

    passport = create_registry_and_passport(client, headers)

    create_response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Registry supporting document",
            "description": "Test evidence for retrieval workflow.",
            "source": "SAL Registry",
            "reference": "EVIDENCE-RETRIEVAL-001",
        },
        headers=headers,
    )

    assert create_response.status_code == 201, create_response.text

    evidence = create_response.json()

    list_response = client.get(
        f"/evidence/{passport['id']}",
        headers=headers,
    )

    assert list_response.status_code == 200, list_response.text

    records = list_response.json()

    assert len(records) == 1
    assert records[0]["evidence_id"] == evidence["evidence_id"]
    assert records[0]["title"] == "Registry supporting document"
    assert records[0]["passport_id"] == passport["id"]

    get_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}",
        headers=headers,
    )

    assert get_response.status_code == 200, get_response.text

    retrieved = get_response.json()

    assert retrieved["evidence_id"] == evidence["evidence_id"]
    assert retrieved["passport_id"] == passport["id"]
    assert retrieved["evidence_type"] == "DOCUMENT"
    assert retrieved["status"] == "SUBMITTED"


def test_evidence_requires_existing_passport(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-invalid-passport@sal.test",
    )

    response = client.post(
        "/evidence/999999",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Invalid passport evidence",
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset Passport not found"


def test_get_nonexistent_evidence_returns_404(client, test_db):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "evidence-not-found@sal.test",
    )

    response = client.get(
        "/evidence/item/SAL-EVIDENCE-NOT-FOUND",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Evidence not found"


def create_test_evidence(client, test_db, role="admin", email="review-admin@sal.test"):
    headers = create_user_and_login(
        client,
        test_db,
        role,
        email,
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        json={
            "evidence_type": "DOCUMENT",
            "title": "Review workflow evidence",
            "description": "Evidence used for review workflow testing.",
            "source": "SAL Review Tests",
            "reference": f"{email}-evidence",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text

    return headers, passport, response.json()


def test_admin_can_review_evidence_through_full_verification_flow(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-full-admin@sal.test",
    )

    assert evidence["status"] == "SUBMITTED"
    assert evidence["version"] == 1

    review_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reason": "Initial evidence review started",
            "reference": "REVIEW-FULL-001",
        },
        headers=headers,
    )

    assert review_response.status_code == 200, review_response.text

    reviewed = review_response.json()

    assert reviewed["status"] == "UNDER_REVIEW"
    assert reviewed["version"] == 2

    verify_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 2,
            "reason": "Evidence passed SAL review",
            "reference": "REVIEW-FULL-002",
        },
        headers=headers,
    )

    assert verify_response.status_code == 200, verify_response.text

    verified = verify_response.json()

    assert verified["status"] == "VERIFIED"
    assert verified["version"] == 3


def test_registrar_can_reject_evidence_after_review(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "registrar",
        "review-reject-registrar@sal.test",
    )

    review_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reason": "Registrar started review",
            "reference": "REVIEW-REJECT-001",
        },
        headers=headers,
    )

    assert review_response.status_code == 200, review_response.text

    reject_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "REJECTED",
            "expected_version": 2,
            "reason": "Evidence does not satisfy review requirements",
            "reference": "REVIEW-REJECT-002",
        },
        headers=headers,
    )

    assert reject_response.status_code == 200, reject_response.text

    rejected = reject_response.json()

    assert rejected["status"] == "REJECTED"
    assert rejected["version"] == 3


def test_viewer_cannot_review_evidence(
    client,
    test_db,
):
    admin_headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-viewer-setup@sal.test",
    )

    viewer_headers = create_user_and_login(
        client,
        test_db,
        "viewer",
        "review-viewer@sal.test",
    )

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-VIEWER-001",
        },
        headers=viewer_headers,
    )

    assert response.status_code == 403


def test_government_cannot_review_evidence(
    client,
    test_db,
):
    admin_headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-government-setup@sal.test",
    )

    government_headers = create_user_and_login(
        client,
        test_db,
        "government",
        "review-government@sal.test",
    )

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-GOVERNMENT-001",
        },
        headers=government_headers,
    )

    assert response.status_code == 403


def test_unauthenticated_user_cannot_review_evidence(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-unauth-setup@sal.test",
    )

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-UNAUTH-001",
        },
    )

    assert response.status_code == 401


def test_invalid_evidence_review_transition_is_rejected(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-invalid-transition@sal.test",
    )

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 1,
            "reference": "REVIEW-INVALID-001",
        },
        headers=headers,
    )

    assert response.status_code == 409

    assert "Invalid Evidence review transition" in response.json()["detail"]


def test_stale_evidence_version_is_rejected(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-stale-version@sal.test",
    )

    first_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-STALE-001",
        },
        headers=headers,
    )

    assert first_response.status_code == 200, first_response.text

    stale_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 1,
            "reference": "REVIEW-STALE-002",
        },
        headers=headers,
    )

    assert stale_response.status_code == 409
    assert (
        stale_response.json()["detail"]
        == "Evidence was modified by another transaction; "
        "retry with the current Evidence state"
    )

    get_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}",
        headers=headers,
    )

    assert get_response.status_code == 200

    current = get_response.json()

    assert current["status"] == "UNDER_REVIEW"
    assert current["version"] == 2


def test_duplicate_evidence_review_reference_is_rejected(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-duplicate-reference@sal.test",
    )

    first_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-DUPLICATE-001",
        },
        headers=headers,
    )

    assert first_response.status_code == 200, first_response.text

    second_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 2,
            "reference": "REVIEW-DUPLICATE-001",
        },
        headers=headers,
    )

    assert second_response.status_code == 409
    assert (
        second_response.json()["detail"]
        == "Evidence review reference already exists"
    )

    get_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}",
        headers=headers,
    )

    assert get_response.status_code == 200

    current = get_response.json()

    assert current["status"] == "UNDER_REVIEW"
    assert current["version"] == 2


def test_evidence_review_history_is_recorded(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-history@sal.test",
    )

    first_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reason": "Review started",
            "reference": "REVIEW-HISTORY-001",
        },
        headers=headers,
    )

    assert first_response.status_code == 200, first_response.text

    second_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 2,
            "reason": "Evidence verified",
            "reference": "REVIEW-HISTORY-002",
        },
        headers=headers,
    )

    assert second_response.status_code == 200, second_response.text

    history_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/review-history",
        headers=headers,
    )

    assert history_response.status_code == 200, history_response.text

    history = history_response.json()

    assert len(history) == 2

    assert history[0]["from_status"] == "SUBMITTED"
    assert history[0]["to_status"] == "UNDER_REVIEW"
    assert history[0]["reason"] == "Review started"
    assert history[0]["reference"] == "REVIEW-HISTORY-001"

    assert history[1]["from_status"] == "UNDER_REVIEW"
    assert history[1]["to_status"] == "VERIFIED"
    assert history[1]["reason"] == "Evidence verified"
    assert history[1]["reference"] == "REVIEW-HISTORY-002"


def test_verified_evidence_is_immutable(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-verified-immutable@sal.test",
    )

    first_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-IMMUTABLE-001",
        },
        headers=headers,
    )

    assert first_response.status_code == 200, first_response.text

    verify_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 2,
            "reference": "REVIEW-IMMUTABLE-002",
        },
        headers=headers,
    )

    assert verify_response.status_code == 200, verify_response.text

    immutable_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "REJECTED",
            "expected_version": 3,
            "reference": "REVIEW-IMMUTABLE-003",
        },
        headers=headers,
    )

    assert immutable_response.status_code == 409

    current_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}",
        headers=headers,
    )

    assert current_response.status_code == 200

    current = current_response.json()

    assert current["status"] == "VERIFIED"
    assert current["version"] == 3


def test_rejected_evidence_is_immutable(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-rejected-immutable@sal.test",
    )

    first_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reference": "REVIEW-REJECT-IMMUTABLE-001",
        },
        headers=headers,
    )

    assert first_response.status_code == 200, first_response.text

    reject_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "REJECTED",
            "expected_version": 2,
            "reference": "REVIEW-REJECT-IMMUTABLE-002",
        },
        headers=headers,
    )

    assert reject_response.status_code == 200, reject_response.text

    immutable_response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "VERIFIED",
            "expected_version": 3,
            "reference": "REVIEW-REJECT-IMMUTABLE-003",
        },
        headers=headers,
    )

    assert immutable_response.status_code == 409

    current_response = client.get(
        f"/evidence/item/{evidence['evidence_id']}",
        headers=headers,
    )

    assert current_response.status_code == 200

    current = current_response.json()

    assert current["status"] == "REJECTED"
    assert current["version"] == 3

def test_evidence_review_creates_audit_event(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "admin",
        "review-audit-event@sal.test",
    )

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reason": "Start evidence audit integration test",
            "reference": "REVIEW-AUDIT-EVENT-001",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    from app.models.audit_event import AuditEvent

    audit_event = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "ASSET_EVIDENCE",
            AuditEvent.entity_id == evidence["evidence_id"],
            AuditEvent.reference == "REVIEW-AUDIT-EVENT-001",
        )
        .first()
    )

    assert audit_event is not None

    assert audit_event.action == "EVIDENCE_REVIEW"
    assert audit_event.actor_type == "USER"
    assert audit_event.source == "API"
    assert audit_event.result == "SUCCESS"

    assert audit_event.asset_registry_id is not None
    assert audit_event.passport_id == passport["id"]

    assert audit_event.before_data is not None
    assert audit_event.after_data is not None
    assert audit_event.audit_metadata is not None


def test_evidence_review_audit_event_records_authenticated_actor(
    client,
    test_db,
):
    headers, passport, evidence = create_test_evidence(
        client,
        test_db,
        "registrar",
        "review-audit-actor@sal.test",
    )

    from app.models.user import User

    user = (
        test_db.query(User)
        .filter(User.email == "review-audit-actor@sal.test")
        .first()
    )

    assert user is not None

    response = client.patch(
        f"/evidence/item/{evidence['evidence_id']}/review",
        json={
            "status": "UNDER_REVIEW",
            "expected_version": 1,
            "reason": "Verify authenticated audit actor",
            "reference": "REVIEW-AUDIT-ACTOR-001",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    from app.models.audit_event import AuditEvent

    audit_event = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "ASSET_EVIDENCE",
            AuditEvent.entity_id == evidence["evidence_id"],
            AuditEvent.reference == "REVIEW-AUDIT-ACTOR-001",
        )
        .first()
    )

    assert audit_event is not None
    assert audit_event.actor_id == user.id
    assert audit_event.actor_type == "USER"
    assert audit_event.source == "API"



def test_evidence_accepts_and_returns_valid_sha256_fingerprint(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "fingerprint-valid@sal.test",
    )

    passport = create_registry_and_passport(client, headers)
    fingerprint = "a" * 64

    response = client.post(
        f"/evidence/{passport['id']}",
        headers=headers,
        json={
            "evidence_type": "DOCUMENT",
            "title": "SHA-256 Evidence",
            "fingerprint_sha256": fingerprint,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["fingerprint_sha256"] == fingerprint


def test_evidence_normalizes_sha256_fingerprint_to_lowercase(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "fingerprint-normalize@sal.test",
    )

    passport = create_registry_and_passport(client, headers)
    fingerprint = "ABCDEF" * 10 + "ABCD"

    assert len(fingerprint) == 64

    response = client.post(
        f"/evidence/{passport['id']}",
        headers=headers,
        json={
            "evidence_type": "DOCUMENT",
            "title": "Normalized SHA-256 Evidence",
            "fingerprint_sha256": fingerprint,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["fingerprint_sha256"] == fingerprint.lower()


def test_invalid_sha256_fingerprint_is_rejected(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "fingerprint-invalid@sal.test",
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        headers=headers,
        json={
            "evidence_type": "DOCUMENT",
            "title": "Invalid Fingerprint Evidence",
            "fingerprint_sha256": "not-a-valid-sha256",
        },
    )

    assert response.status_code == 422


def test_evidence_fingerprint_is_optional_for_metadata_only_evidence(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "fingerprint-optional@sal.test",
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}",
        headers=headers,
        json={
            "evidence_type": "NOTE",
            "title": "Metadata Only Evidence",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["fingerprint_sha256"] is None
