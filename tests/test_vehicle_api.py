from app.core.security import hash_password
from app.models.asset_registry import AssetRegistry
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
        full_name=f"SAL Vehicle {role.title()}",
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


def test_create_vehicle_persists_chassis_and_sal_identity(
    client,
    test_db,
):
    headers = create_user_and_login(
        client,
        test_db,
        email="vehicle-create@sal.test",
        role="admin",
        password="SAL-Vehicle-Create-2026",
    )

    payload = {
        "owner": "SAL Vehicle Test Owner",
        "registration_number": "GT-TEST-001",
        "vin": "SALVINTEST00000001",
        "chassis_number": "CHASSISTEST00000001",
        "manufacturer": "Mercedes-Benz",
        "model": "G-Class",
        "year": 2026,
        "engine_number": "ENGTEST00000001",
        "color": "Black",
        "estimated_value": 150000.0,
    }

    response = client.post(
        "/vehicles/",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["chassis_number"] == "CHASSISTEST00000001"
    assert data["vin"] == "SALVINTEST00000001"
    assert data["registration_number"] == "GT-TEST-001"

    vehicle_id = data["id"]

    registry = (
        test_db.query(AssetRegistry)
        .filter(
            AssetRegistry.registry_id == vehicle_id,
            AssetRegistry.asset_type == "Vehicle",
        )
        .one()
    )

    assert registry.sal_id.startswith("SAL-")
    assert len(registry.sal_id) == 28
    assert registry.owner == "SAL Vehicle Test Owner"
    assert registry.government_verification == "NOT_VERIFIED"
    assert registry.sal_verification == "VERIFIED"
