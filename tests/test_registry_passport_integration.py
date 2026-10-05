from app.models.user import User
from app.core.security import hash_password


def test_registry_to_passport_flow(client, test_db):
    test_password = "SAL-Test-Registry-2026"

    admin = User(
        full_name="SAL Registry Test Administrator",
        email="registry-admin@sal.test",
        password=hash_password(test_password),
        role="admin",
    )

    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)

    # 1. Authenticate
    login_response = client.post(
        "/users/login",
        data={
            "username": "registry-admin@sal.test",
            "password": test_password,
        },
    )

    assert login_response.status_code == 200

    token_data = login_response.json()
    token = token_data["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    # 2. Create the SAL asset identity in the registry
    registry_response = client.post(
        "/registry/",
        json={
            "asset_type": "Land",
            "registry_id": 900001,
            "owner": "SAL Integration Test Owner",
            "estimated_value": 300000,
            "status": "Active",
        },
        headers=headers,
    )

    assert registry_response.status_code == 200, registry_response.text

    registry_data = registry_response.json()

    assert registry_data["registry_id"] == 900001
    assert registry_data["asset_type"] == "Land"
    assert registry_data["owner"] == "SAL Integration Test Owner"

    sal_id = registry_data["sal_id"]

    assert sal_id
    assert sal_id.startswith("SAL-")

    # 3. Create the Asset Passport
    passport_response = client.post(
        f"/passport/{sal_id}",
        headers=headers,
    )

    assert passport_response.status_code == 201, passport_response.text

    passport_data = passport_response.json()

    assert passport_data["sal_id"] == sal_id
    assert passport_data["asset_type"] == "Land"
    assert passport_data["owner"] == "SAL Integration Test Owner"
    assert passport_data["lifecycle_state"] == "REGISTERED"
    assert passport_data["status"] == "ACTIVE"
    assert passport_data["version"] == 1

    passport_id = passport_data["passport_id"]

    assert passport_id
    assert passport_id.startswith("SAL-PASSPORT-")

    # 4. Retrieve the Passport using the SAL ID
    get_response = client.get(
        f"/passport/{sal_id}",
        headers=headers,
    )

    assert get_response.status_code == 200, get_response.text

    retrieved = get_response.json()

    assert retrieved["passport_id"] == passport_id
    assert retrieved["sal_id"] == sal_id
    assert retrieved["asset_type"] == "Land"
    assert retrieved["owner"] == "SAL Integration Test Owner"
    assert retrieved["lifecycle_state"] == "REGISTERED"

    # 5. Passport creation must be idempotent/protected against duplicates
    duplicate_response = client.post(
        f"/passport/{sal_id}",
        headers=headers,
    )

    assert duplicate_response.status_code == 409
