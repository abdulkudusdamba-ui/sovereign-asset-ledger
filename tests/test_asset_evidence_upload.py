import hashlib

import pytest


def create_user_and_login(client, test_db, role, email):
    from app.core.security import hash_password
    from app.models.user import User

    password = "SAL-Test-Upload-2026"

    user = User(
        full_name=f"Upload {role.title()}",
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
            "registry_id": 930001,
            "owner": "SAL Upload Test Owner",
            "estimated_value": 500000,
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


def test_admin_can_upload_evidence_file(
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
        "upload-admin@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    content = b" SAL evidence test file - immutable content "

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "TITLE_DOCUMENT",
            "title": "Land Title Evidence",
            "description": "Test uploaded evidence",
            "source": "Lands Commission",
            "reference": "LC-TEST-001",
        },
        files={
            "file": (
                "land-title.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text

    data = response.json()

    expected_hash = hashlib.sha256(content).hexdigest()

    assert data["evidence_id"].startswith("SAL-EVIDENCE-")
    assert data["passport_id"] == passport["id"]
    assert data["evidence_type"] == "TITLE_DOCUMENT"
    assert data["title"] == "Land Title Evidence"
    assert data["storage_backend"] == "local"
    assert data["storage_key"] == f"{data['evidence_id']}.bin"
    assert data["original_filename"] == "land-title.txt"
    assert data["content_type"] == "text/plain"
    assert data["size_bytes"] == len(content)
    assert data["fingerprint_sha256"] == expected_hash
    assert data["status"] == "SUBMITTED"
    assert data["submitted_by"] == "upload-admin@example.com"

    stored_file = tmp_path / f"{data['evidence_id']}.bin"

    assert stored_file.exists()
    assert stored_file.read_bytes() == content


def test_registrar_can_upload_evidence_file(
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
        "registrar",
        "upload-registrar@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    content = b"Registrar uploaded evidence"

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "IDENTITY_DOCUMENT",
            "title": "Owner Identity Evidence",
        },
        files={
            "file": (
                "identity.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["submitted_by"] == "upload-registrar@example.com"


@pytest.mark.parametrize(
    "role",
    ["viewer", "government"],
)
def test_unauthorized_roles_cannot_upload(
    client,
    test_db,
    role,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "SAL_EVIDENCE_STORAGE_ROOT",
        str(tmp_path),
    )

    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        f"upload-{role}-passport-admin@example.com",
    )

    passport = create_registry_and_passport(
        client,
        admin_headers,
    )

    restricted_headers = create_user_and_login(
        client,
        test_db,
        role,
        f"upload-{role}@example.com",
    )

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=restricted_headers,
        data={
            "evidence_type": "OTHER",
            "title": "Unauthorized Upload",
        },
        files={
            "file": (
                "blocked.txt",
                b"should not be stored",
                "text/plain",
            )
        },
    )

    assert response.status_code == 403
    assert not list(tmp_path.glob('*.bin'))


def test_unauthenticated_user_cannot_upload(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "SAL_EVIDENCE_STORAGE_ROOT",
        str(tmp_path),
    )

    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "upload-owner@example.com",
    )

    passport = create_registry_and_passport(
        client,
        admin_headers,
    )

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        data={
            "evidence_type": "OTHER",
            "title": "Unauthenticated Upload",
        },
        files={
            "file": (
                "blocked.txt",
                b"should not be stored",
                "text/plain",
            )
        },
    )

    assert response.status_code == 401
    assert not list(tmp_path.glob('*.bin'))


def test_upload_rejects_unknown_passport(
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
        "upload-missing-passport@example.com",
    )

    response = client.post(
        "/evidence/999999/upload",
        headers=headers,
        data={
            "evidence_type": "OTHER",
            "title": "Missing Passport",
        },
        files={
            "file": (
                "missing.txt",
                b"should not be stored",
                "text/plain",
            )
        },
    )

    assert response.status_code == 404
    assert not list(tmp_path.glob('*.bin'))


def test_upload_rejects_fingerprint_mismatch(
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
        "upload-fingerprint@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    content = b"correct content"

    wrong_hash = hashlib.sha256(
        b"different content"
    ).hexdigest()

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "OTHER",
            "title": "Fingerprint Test",
            "fingerprint_sha256": wrong_hash,
        },
        files={
            "file": (
                "fingerprint.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 422
    assert "fingerprint" in response.json()["detail"].lower()
    assert not list(tmp_path.glob('*.bin'))


def test_upload_rejects_file_over_10_mib(
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
        "upload-large@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    oversized_content = b"x" * (10 * 1024 * 1024 + 1)

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "OTHER",
            "title": "Oversized Evidence",
        },
        files={
            "file": (
                "oversized.bin",
                oversized_content,
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 413
    assert "10 MiB" in response.json()["detail"]
    assert not list(tmp_path.glob('*.bin'))


def test_upload_rejects_empty_required_text(
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
        "upload-empty-text@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "   ",
            "title": "Valid Title",
        },
        files={
            "file": (
                "empty-type.txt",
                b"content",
                "text/plain",
            )
        },
    )

    assert response.status_code == 422
    assert "evidence_type" in response.json()["detail"]
    assert not list(tmp_path.glob('*.bin'))


def test_upload_accepts_matching_client_fingerprint(
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
        "upload-matching-fingerprint@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    content = b"fingerprint matches"
    expected_hash = hashlib.sha256(content).hexdigest()

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "OTHER",
            "title": "Matching Fingerprint",
            "fingerprint_sha256": expected_hash.upper(),
        },
        files={
            "file": (
                "matching.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["fingerprint_sha256"] == expected_hash


def test_upload_cleans_up_file_when_database_persistence_fails(
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
        "upload-db-failure@example.com",
    )

    passport = create_registry_and_passport(
        client,
        headers,
    )

    original_commit = test_db.commit

    def failing_commit():
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(
        test_db,
        "commit",
        failing_commit,
    )

    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "OTHER",
            "title": "Database Failure Cleanup Test",
        },
        files={
            "file": (
                "cleanup.txt",
                b"file must be cleaned up",
                "text/plain",
            )
        },
    )

    assert response.status_code == 409
    assert "database persistence failed" in response.json()["detail"]

    assert not list(tmp_path.glob("*.bin"))

    monkeypatch.setattr(
        test_db,
        "commit",
        original_commit,
    )
