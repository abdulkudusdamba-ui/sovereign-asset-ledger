from app.models.user import User
from app.core.security import hash_password


def test_admin_login_and_authenticated_access(client, test_db):
    test_password = "SAL-Test-Admin-2026"

    admin = User(
        full_name="SAL Test Administrator",
        email="test-admin@sal.test",
        password=hash_password(test_password),
        role="admin",
    )

    test_db.add(admin)
    test_db.commit()
    test_db.refresh(admin)

    login_response = client.post(
        "/users/login",
        data={
            "username": "test-admin@sal.test",
            "password": test_password,
        },
    )

    assert login_response.status_code == 200

    token_data = login_response.json()

    assert token_data["access_token"]
    assert token_data["token_type"] == "bearer"

    token = token_data["access_token"]

    protected_response = client.get(
        "/passport/TEST-SAL-ID",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert protected_response.status_code == 404
    assert protected_response.json()["detail"] == "SAL asset identity not found"
