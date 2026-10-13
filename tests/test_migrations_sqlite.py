import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parent.parent


def test_fresh_sqlite_migration_has_single_head_and_audit_triggers(tmp_path):
    db = tmp_path / "mig.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db}"}
    heads = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    assert len(heads.stdout.strip().splitlines()) == 1
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT, env=env, check=True, capture_output=True,
    )
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        names = {r[0] for r in conn.execute(sa.text(
            "select name from sqlite_master where type='trigger'"))}
        assert {"trg_audit_events_prevent_update",
                "trg_audit_events_prevent_delete"} <= names
    engine.dispose()
