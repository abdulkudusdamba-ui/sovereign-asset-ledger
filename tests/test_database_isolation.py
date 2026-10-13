import os
import subprocess
import sys
from pathlib import Path

from app.models.user import User

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_importing_application_does_not_touch_default_database():
    default_database = PROJECT_ROOT / "sal.db"
    original_contents = (
        default_database.read_bytes() if default_database.exists() else None
    )
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{default_database}"

    subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    current_contents = (
        default_database.read_bytes() if default_database.exists() else None
    )
    assert current_contents == original_contents


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
