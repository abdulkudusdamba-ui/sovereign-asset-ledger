"""
Migration 010
Add storage metadata to SAL Evidence.

This migration:
1. Backs up the database.
2. Verifies the asset_evidence table exists.
3. Verifies the existing Evidence schema.
4. Adds storage metadata columns.
5. Creates indexes needed for storage lookups.
6. Verifies existing Evidence records are preserved.
7. Runs foreign-key and database integrity checks.

This migration does not store file bytes in SQLite.
Actual Evidence content remains in the configured storage backend.
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
        ROOT / f"sal.db.backup-migration-010-{timestamp}.db"
    )
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def fail(message: str):
    raise RuntimeError(message)


def migrate():
    print("===== SAL MIGRATION 010: EVIDENCE STORAGE METADATA =====")

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
        # 2. Verify existing Evidence schema
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
            "submitted_by",
            "created_at",
            "version",
            "fingerprint_sha256",
        }

        missing = required_columns - columns

        if missing:
            fail(
                "asset_evidence is missing required columns: "
                + ", ".join(sorted(missing))
            )

        print("[PASS] Existing Evidence schema verified")

        # ---------------------------------------------------------
        # 3. Add storage backend
        # ---------------------------------------------------------
        if "storage_backend" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN storage_backend VARCHAR
                """
            )
            print(
                "[PASS] asset_evidence.storage_backend column added"
            )
        else:
            print(
                "[INFO] asset_evidence.storage_backend "
                "already exists"
            )

        # ---------------------------------------------------------
        # 4. Add storage key
        # ---------------------------------------------------------
        if "storage_key" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN storage_key VARCHAR
                """
            )
            print(
                "[PASS] asset_evidence.storage_key column added"
            )
        else:
            print(
                "[INFO] asset_evidence.storage_key "
                "already exists"
            )

        # ---------------------------------------------------------
        # 5. Add original filename
        # ---------------------------------------------------------
        if "original_filename" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN original_filename VARCHAR
                """
            )
            print(
                "[PASS] asset_evidence.original_filename column added"
            )
        else:
            print(
                "[INFO] asset_evidence.original_filename "
                "already exists"
            )

        # ---------------------------------------------------------
        # 6. Add content type
        # ---------------------------------------------------------
        if "content_type" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN content_type VARCHAR
                """
            )
            print(
                "[PASS] asset_evidence.content_type column added"
            )
        else:
            print(
                "[INFO] asset_evidence.content_type "
                "already exists"
            )

        # ---------------------------------------------------------
        # 7. Add size in bytes
        # ---------------------------------------------------------
        if "size_bytes" not in columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN size_bytes INTEGER
                """
            )
            print(
                "[PASS] asset_evidence.size_bytes column added"
            )
        else:
            print(
                "[INFO] asset_evidence.size_bytes "
                "already exists"
            )

        conn.commit()

        # ---------------------------------------------------------
        # 8. Create storage lookup indexes
        # ---------------------------------------------------------
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_storage_backend
            ON asset_evidence(storage_backend)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_storage_key
            ON asset_evidence(storage_key)
            """
        )

        conn.commit()

        print("[PASS] Evidence storage indexes verified")

        # ---------------------------------------------------------
        # 9. Verify all new columns
        # ---------------------------------------------------------
        columns_after = {
            row[1]: row
            for row in conn.execute(
                "PRAGMA table_info(asset_evidence)"
            ).fetchall()
        }

        expected_storage_columns = {
            "storage_backend",
            "storage_key",
            "original_filename",
            "content_type",
            "size_bytes",
        }

        missing_storage_columns = (
            expected_storage_columns
            - set(columns_after.keys())
        )

        if missing_storage_columns:
            fail(
                "Migration verification failed. Missing storage "
                "columns: "
                + ", ".join(sorted(missing_storage_columns))
            )

        print("[PASS] Evidence storage metadata schema verified")

        # ---------------------------------------------------------
        # 10. Verify existing Evidence records were preserved
        # ---------------------------------------------------------
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM asset_evidence"
        ).fetchone()[0]

        metadata_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM asset_evidence
            WHERE storage_key IS NOT NULL
            """
        ).fetchone()[0]

        invalid_sizes = conn.execute(
            """
            SELECT COUNT(*)
            FROM asset_evidence
            WHERE size_bytes IS NOT NULL
              AND size_bytes < 0
            """
        ).fetchone()[0]

        if invalid_sizes != 0:
            fail(
                "Invalid negative Evidence size_bytes values found: "
                f"{invalid_sizes}"
            )

        print(
            f"[INFO] Evidence records preserved: {evidence_count}"
        )

        print(
            "[INFO] Evidence records with storage metadata: "
            f"{metadata_count}"
        )

        # ---------------------------------------------------------
        # 11. Verify indexes
        # ---------------------------------------------------------
        indexes = {
            row[1]
            for row in conn.execute(
                "PRAGMA index_list(asset_evidence)"
            ).fetchall()
        }

        required_indexes = {
            "ix_asset_evidence_storage_backend",
            "ix_asset_evidence_storage_key",
        }

        missing_indexes = required_indexes - indexes

        if missing_indexes:
            fail(
                "Migration verification failed. Missing indexes: "
                + ", ".join(sorted(missing_indexes))
            )

        print("[PASS] Evidence storage indexes verified")

        # ---------------------------------------------------------
        # 12. Foreign-key integrity
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
        # 13. Database integrity
        # ---------------------------------------------------------
        integrity = conn.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            fail(
                f"SQLite integrity_check failed: {integrity}"
            )

        print("[PASS] SQLite integrity_check passed")

    except Exception:
        conn.rollback()
        print()
        print("MIGRATION 010 FAILED.")
        print("Database transaction rolled back.")
        print(f"Backup remains available at: {backup_path}")
        raise

    finally:
        conn.close()

    print()
    print("================================================")
    print("MIGRATION 010 PASSED")
    print("================================================")


if __name__ == "__main__":
    migrate()
