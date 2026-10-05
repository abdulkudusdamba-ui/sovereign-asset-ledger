from app.models.user import User


def test_database_isolation(test_db):
    user = User(
        full_name="Test Isolation User",
        email="isolation@example.test",
        password="test-password",
        role="viewer",
    )

    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    assert user.id is not None
    assert user.email == "isolation@example.test"

    found = test_db.query(User).filter(
        User.email == "isolation@example.test"
    ).first()

    assert found is not None
    assert found.email == "isolation@example.test"
