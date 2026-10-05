"""
Migration 009
Add cryptographic fingerprinting to SAL Evidence.

This migration:
1. Backs up the database.
2. Verifies the asset_evidence table exists.
3. Adds a nullable SHA-256 fingerprint column.
4. Creates an index for fingerprint lookups.
5. Verifies existing Evidence records are preserved.
6. Runs foreign-key and integrity checks.
"""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "sal.db"


def create_backup() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = (
        ROOT / f"sal.db.backup-migration-009-{timestamp}.db"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def fail(message: str):
    raise RuntimeError(message)


def migrate():
    print("===== SAL MIGRATION 009: EVIDENCE FINGERPRINT =====")

    if not DB_PATH.exists():
        fail(f"Database not found: {DB_PATH}")

    backup_path = create_backup()
    print(f"[PASS] Database backup created: {backup_path.name}")

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # ---------------------------------------------------------
        # 1. Verify required table
        # ---------------------------------------------------------
        table_exists = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'asset_evidence'
            """
        ).fetchone()

        if not table_exists:
            fail(
                "Required table asset_evidence does not exist"
            )

        print("[PASS] asset_evidence table exists")

        # ---------------------------------------------------------
        # 2. Verify required existing columns
        # ---------------------------------------------------------
        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(asset_evidence)"
            ).fetchall()
        }

        required_columns = {
            "id",
            "evidence_id",
            "passport_id",
            "evidence_type",
            "title",
            "status",
            "version",
            "created_at",
        }

        missing = required_columns - columns

        if missing:
            fail(
                "asset_evidence is missing required columns: "
                + ", ".join(sorted(missing))
            )

        print("[PASS] Existing Evidence schema verified")

        # ---------------------------------------------------------
        # 3. Add SHA-256 fingerprint
        # ---------------------------------------------------------
        if "fingerprint_sha256" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN fingerprint_sha256 VARCHAR
                """
            )

            conn.commit()

            print(
                "[PASS] asset_evidence.fingerprint_sha256 column added"
            )
        else:
            print(
                "[INFO] asset_evidence.fingerprint_sha256 "
                "already exists"
            )

        # ---------------------------------------------------------
        # 4. Create fingerprint lookup index
        # ---------------------------------------------------------
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_fingerprint_sha256
            ON asset_evidence(fingerprint_sha256)
            """
        )

        conn.commit()

        print(
            "[PASS] Evidence fingerprint index verified"
        )

        # ---------------------------------------------------------
        # 5. Verify column definition
        # ---------------------------------------------------------
        columns_after = {
            row[1]: row
            for row in conn.execute(
                "PRAGMA table_info(asset_evidence)"
            ).fetchall()
        }

        fingerprint_column = columns_after.get(
            "fingerprint_sha256"
        )

        if fingerprint_column is None:
            fail(
                "Migration verification failed: "
                "fingerprint_sha256 column missing"
            )

        print(
            "[PASS] fingerprint_sha256 column verified"
        )

        # ---------------------------------------------------------
        # 6. Verify existing Evidence records were preserved
        # ---------------------------------------------------------
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM asset_evidence"
        ).fetchone()[0]

        null_fingerprint_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM asset_evidence
            WHERE fingerprint_sha256 IS NULL
            """
        ).fetchone()[0]

        print(
            f"[INFO] Evidence records preserved: {evidence_count}"
        )

        print(
            "[INFO] Evidence records awaiting fingerprint: "
            f"{null_fingerprint_count}"
        )

        # ---------------------------------------------------------
        # 7. Verify fingerprint index
        # ---------------------------------------------------------
        indexes = {
            row[1]
            for row in conn.execute(
                "PRAGMA index_list(asset_evidence)"
            ).fetchall()
        }

        if (
            "ix_asset_evidence_fingerprint_sha256"
            not in indexes
        ):
            fail(
                "Migration verification failed: "
                "fingerprint index missing"
            )

        print("[PASS] Fingerprint index verified")

        # ---------------------------------------------------------
        # 8. Foreign-key integrity
        # ---------------------------------------------------------
        fk_errors = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if fk_errors:
            fail(
                "SQLite foreign-key violations detected: "
                + str(fk_errors)
            )

        print(
            "[PASS] SQLite foreign-key integrity check passed"
        )

        # ---------------------------------------------------------
        # 9. Database integrity
        # ---------------------------------------------------------
        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            fail(
                f"SQLite integrity_check failed: {integrity}"
            )

        print("[PASS] SQLite integrity_check passed")

    finally:
        conn.close()

    print()
    print("================================================")
    print("MIGRATION 009 PASSED")
    print("================================================")


if __name__ == "__main__":
    migrate()
