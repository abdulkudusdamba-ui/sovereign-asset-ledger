import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database.database import Base, get_db
from app.main import app
from app.routers.user import get_db as user_get_db


@pytest.fixture()
def test_db(tmp_path):
    database_file = tmp_path / "test_sal.db"

    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS
            trg_audit_events_prevent_update
            BEFORE UPDATE ON audit_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Audit events are immutable and cannot be updated'
                );
            END;
            """
        )

        connection.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS
            trg_audit_events_prevent_delete
            BEFORE DELETE ON audit_events
            BEGIN
                SELECT RAISE(
                    ABORT,
                    'Audit events are immutable and cannot be deleted'
                );
            END;
            """
        )

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture()
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[user_get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
