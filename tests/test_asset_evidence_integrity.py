import hashlib
import json

from app.models.audit_event import AuditEvent


def create_user_and_login(client, test_db, role, email):
    from app.core.security import hash_password
    from app.models.user import User

    password = "SAL-Test-Integrity-2026"

    user = User(
        full_name=f"Integrity {role.title()}",
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
            "registry_id": 940001,
            "owner": "SAL Integrity Test Owner",
            "estimated_value": 600000,
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


def upload_evidence(
    client,
    passport,
    headers,
    content,
):
    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "TITLE_DOCUMENT",
            "title": "Integrity Test Evidence",
            "source": "SAL Integrity Test",
            "reference": "INTEGRITY-TEST-001",
        },
        files={
            "file": (
                "integrity.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def test_uploaded_evidence_integrity_verification_is_valid(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "SAL_EVIDENCE_STORAGE_ROOT",
        str(tmp_path),
    )

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "integrity-valid@example.com",
    )

    passport = create_registry_and_passport(
        client,
        headers,
    )

    content = b"Immutable SAL evidence content"
    evidence = upload_evidence(
        client,
        passport,
        headers,
        content,
    )

    expected_hash = hashlib.sha256(content).hexdigest()

    assert evidence["fingerprint_sha256"] == expected_hash

    response = client.post(
        f"/evidence/item/{evidence['evidence_id']}/verify-integrity",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["evidence_id"] == evidence["evidence_id"]
    assert data["stored_fingerprint_sha256"] == expected_hash
    assert data["recorded_fingerprint_sha256"] == expected_hash
    assert data["result"] == "INTEGRITY_VALID"


def test_modified_evidence_fails_integrity_verification(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "SAL_EVIDENCE_STORAGE_ROOT",
        str(tmp_path),
    )

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "integrity-failed@example.com",
    )

    passport = create_registry_and_passport(
        client,
        headers,
    )

    original_content = b"Original immutable evidence"
    evidence = upload_evidence(
        client,
        passport,
        headers,
        original_content,
    )

    stored_file = tmp_path / f"{evidence['evidence_id']}.bin"

    assert stored_file.exists()

    stored_file.write_bytes(
        b"Tampered evidence content"
    )

    response = client.post(
        f"/evidence/item/{evidence['evidence_id']}/verify-integrity",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    tampered_hash = hashlib.sha256(
        b"Tampered evidence content"
    ).hexdigest()

    original_hash = hashlib.sha256(
        original_content
    ).hexdigest()

    assert data["evidence_id"] == evidence["evidence_id"]
    assert data["stored_fingerprint_sha256"] == tampered_hash
    assert data["recorded_fingerprint_sha256"] == original_hash
    assert data["result"] == "INTEGRITY_FAILED"


def test_integrity_verification_records_audit_event(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "SAL_EVIDENCE_STORAGE_ROOT",
        str(tmp_path),
    )

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "integrity-audit@example.com",
    )

    passport = create_registry_and_passport(
        client,
        headers,
    )

    evidence = upload_evidence(
        client,
        passport,
        headers,
        b"Audit verification evidence",
    )

    response = client.post(
        f"/evidence/item/{evidence['evidence_id']}/verify-integrity",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    audit_event = (
        test_db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "ASSET_EVIDENCE",
            AuditEvent.entity_id == evidence["evidence_id"],
            AuditEvent.action == "VERIFY_INTEGRITY",
        )
        .order_by(AuditEvent.id.desc())
        .first()
    )

    assert audit_event is not None
    assert audit_event.actor_type == "USER"
    assert audit_event.source == "API"
    assert audit_event.result == "INTEGRITY_VALID"
    assert audit_event.passport_id == passport["id"]

    metadata = json.loads(audit_event.audit_metadata)

    assert metadata["recorded_fingerprint_sha256"] == evidence[
        "fingerprint_sha256"
    ]
    assert metadata["integrity_result"] == "INTEGRITY_VALID"
