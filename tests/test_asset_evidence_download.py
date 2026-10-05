def create_user_and_login(client, test_db, role, email):
    from app.core.security import hash_password
    from app.models.user import User

    password = "SAL-Test-Download-2026"

    user = User(
        full_name=f"Download {role.title()}",
        email=email,
        password=hash_password(password),
        role=role,
    )

    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    response = client.post(
        "/users/login",
        data={"username": email, "password": password},
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
            "registry_id": 950001,
            "owner": "SAL Download Test Owner",
            "estimated_value": 700000,
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


def upload_evidence(client, passport, headers, content):
    response = client.post(
        f"/evidence/{passport['id']}/upload",
        headers=headers,
        data={
            "evidence_type": "TITLE_DOCUMENT",
            "title": "Download Test Evidence",
        },
        files={
            "file": (
                "important-document.txt",
                content,
                "text/plain",
            )
        },
    )

    assert response.status_code == 201, response.text

    return response.json()


def test_authenticated_user_can_download_evidence(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SAL_EVIDENCE_STORAGE_ROOT", str(tmp_path))

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "download-admin@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    content = b"Exact immutable evidence download content"
    evidence = upload_evidence(
        client,
        passport,
        headers,
        content,
    )

    response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/download",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.content == content
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="important-document.txt"'
    )


def test_viewer_can_download_evidence(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SAL_EVIDENCE_STORAGE_ROOT", str(tmp_path))

    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "download-viewer-admin@example.com",
    )

    passport = create_registry_and_passport(client, admin_headers)

    content = b"Viewer download content"
    evidence = upload_evidence(
        client,
        passport,
        admin_headers,
        content,
    )

    viewer_headers = create_user_and_login(
        client,
        test_db,
        "viewer",
        "download-viewer@example.com",
    )

    response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/download",
        headers=viewer_headers,
    )

    assert response.status_code == 200
    assert response.content == content


def test_unauthenticated_user_cannot_download_evidence(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SAL_EVIDENCE_STORAGE_ROOT", str(tmp_path))

    admin_headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "download-unauthenticated-admin@example.com",
    )

    passport = create_registry_and_passport(client, admin_headers)

    evidence = upload_evidence(
        client,
        passport,
        admin_headers,
        b"Protected evidence",
    )

    response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/download"
    )

    assert response.status_code == 401


def test_download_returns_404_for_missing_evidence(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        "viewer",
        "download-missing@example.com",
    )

    response = client.get(
        "/evidence/item/SAL-EVIDENCE-DOES-NOT-EXIST/download",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Evidence not found"


def test_download_returns_404_when_stored_file_is_missing(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SAL_EVIDENCE_STORAGE_ROOT", str(tmp_path))

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "download-file-missing@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    evidence = upload_evidence(
        client,
        passport,
        headers,
        b"File will be removed",
    )

    stored_file = tmp_path / f"{evidence['evidence_id']}.bin"
    assert stored_file.exists()

    stored_file.unlink()

    response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/download",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Evidence file not found"


def test_download_rejects_invalid_storage_metadata(
    client,
    test_db,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("SAL_EVIDENCE_STORAGE_ROOT", str(tmp_path))

    headers = create_user_and_login(
        client,
        test_db,
        "admin",
        "download-invalid-metadata@example.com",
    )

    passport = create_registry_and_passport(client, headers)

    evidence = upload_evidence(
        client,
        passport,
        headers,
        b"Protected metadata test",
    )

    from app.models.asset_evidence import AssetEvidence

    database_evidence = (
        test_db.query(AssetEvidence)
        .filter(
            AssetEvidence.evidence_id == evidence["evidence_id"]
        )
        .first()
    )

    database_evidence.storage_key = "../outside.bin"
    test_db.commit()

    response = client.get(
        f"/evidence/item/{evidence['evidence_id']}/download",
        headers=headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Evidence storage metadata is invalid"
