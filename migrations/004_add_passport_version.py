"""
Migration 004
Add optimistic concurrency versioning to asset_passports.

This migration:
1. Backs up the database.
2. Verifies the asset_passports table exists.
3. Adds a non-null version column with default value 1.
4. Verifies existing Passport records have version 1.
5. Runs foreign-key and integrity checks.
"""

from pathlib import Path
import shutil
import sqlite3
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "sal.db"

if not DB_PATH.exists():
    raise RuntimeError(f"Database not found: {DB_PATH}")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_PATH = ROOT / f"sal.db.backup_before_migration_004_{timestamp}"

shutil.copy2(DB_PATH, BACKUP_PATH)

print("================================================")
print("MIGRATION 004 — ADD PASSPORT VERSION")
print("================================================")
print(f"[INFO] Database: {DB_PATH}")
print(f"[INFO] Backup:   {BACKUP_PATH}")

conn = sqlite3.connect(DB_PATH)

try:
    conn.execute("PRAGMA foreign_keys = ON")

    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'asset_passports'
        """
    ).fetchone()

    if not table_exists:
        raise RuntimeError(
            "Required table asset_passports does not exist"
        )

    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(asset_passports)"
        ).fetchall()
    }

    required_columns = {
        "id",
        "passport_id",
        "asset_registry_id",
        "status",
        "lifecycle_state",
    }

    missing = required_columns - columns

    if missing:
        raise RuntimeError(
            f"asset_passports is missing required columns: {sorted(missing)}"
        )

    if "version" not in columns:
        print("[INFO] Adding asset_passports.version...")

        conn.execute(
            """
            ALTER TABLE asset_passports
            ADD COLUMN version INTEGER NOT NULL DEFAULT 1
            """
        )

        conn.commit()

        print("[PASS] version column added")

    else:
        print("[INFO] version column already exists")

    # Verify column definition.
    columns_after = {
        row[1]: row
        for row in conn.execute(
            "PRAGMA table_info(asset_passports)"
        ).fetchall()
    }

    version_column = columns_after.get("version")

    if version_column is None:
        raise RuntimeError(
            "Migration verification failed: version column missing"
        )

    print(
        "[INFO] version column:",
        version_column,
    )

    # Verify all existing rows.
    invalid_versions = conn.execute(
        """
        SELECT COUNT(*)
        FROM asset_passports
        WHERE version IS NULL
           OR version < 1
        """
    ).fetchone()[0]

    if invalid_versions:
        raise RuntimeError(
            f"Found {invalid_versions} Passport records "
            "with invalid version values"
        )

    passport_count = conn.execute(
        "SELECT COUNT(*) FROM asset_passports"
    ).fetchone()[0]

    print(
        f"[PASS] {passport_count} existing Passport records "
        "have valid version values"
    )

    # Foreign-key integrity.
    fk_errors = conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if fk_errors:
        raise RuntimeError(
            f"Foreign-key violations detected: {fk_errors}"
        )

    print("[PASS] PRAGMA foreign_key_check: no violations")

    # Basic integrity check.
    integrity = conn.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError(
            f"SQLite integrity_check failed: {integrity}"
        )

    print("[PASS] SQLite integrity_check: ok")

finally:
    conn.close()

print()
print("================================================")
print("MIGRATION 004 PASSED")
print("================================================")
