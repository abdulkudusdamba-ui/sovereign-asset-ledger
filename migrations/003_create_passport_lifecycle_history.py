from datetime import datetime
from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "sal.db"

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
BACKUP_PATH = ROOT / f"sal.db.backup-migration-003-{timestamp}.db"


def fail(message: str):
    raise RuntimeError(message)


print("===== SAL MIGRATION 003: PASSPORT LIFECYCLE HISTORY =====")

if not DB_PATH.exists():
    fail(f"Database not found: {DB_PATH}")

shutil.copy2(DB_PATH, BACKUP_PATH)

print(f"[PASS] Database backup created: {BACKUP_PATH.name}")

conn = sqlite3.connect(DB_PATH)

try:
    conn.execute("PRAGMA foreign_keys = ON")

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table'"
        ).fetchall()
    }

    required_tables = {
        "asset_registry",
        "asset_passports",
    }

    missing = required_tables - tables

    if missing:
        fail(
            "Required tables missing: "
            + ", ".join(sorted(missing))
        )

    print("[PASS] Required SAL Passport tables exist")

    passport_columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(asset_passports)"
        ).fetchall()
    }

    required_passport_columns = {
        "id",
        "passport_id",
        "asset_registry_id",
        "status",
        "lifecycle_state",
    }

    missing_passport_columns = (
        required_passport_columns - passport_columns
    )

    if missing_passport_columns:
        fail(
            "asset_passports is missing columns: "
            + ", ".join(sorted(missing_passport_columns))
        )

    print("[PASS] asset_passports schema verified")

    existing_count = conn.execute(
        "SELECT COUNT(*) FROM passport_lifecycle_history"
    ).fetchone()[0] if "passport_lifecycle_history" in tables else 0

    if "passport_lifecycle_history" not in tables:
        conn.execute(
            """
            CREATE TABLE passport_lifecycle_history (
                id INTEGER PRIMARY KEY,
                passport_id INTEGER NOT NULL,
                from_state VARCHAR NOT NULL,
                to_state VARCHAR NOT NULL,
                reason VARCHAR,
                reference VARCHAR,
                changed_by VARCHAR,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (passport_id)
                    REFERENCES asset_passports(id)
            )
            """
        )

        print("[PASS] passport_lifecycle_history table created")
    else:
        print(
            "[INFO] passport_lifecycle_history table already exists"
        )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_passport_lifecycle_history_id
        ON passport_lifecycle_history(id)
        """
    )

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_passport_lifecycle_history_passport_id
        ON passport_lifecycle_history(passport_id)
        """
    )

    conn.commit()

    print("[PASS] Lifecycle history indexes verified")

    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(passport_lifecycle_history)"
        ).fetchall()
    }

    expected_columns = {
        "id",
        "passport_id",
        "from_state",
        "to_state",
        "reason",
        "reference",
        "changed_by",
        "created_at",
    }

    missing_columns = expected_columns - columns

    if missing_columns:
        fail(
            "Lifecycle history table missing columns: "
            + ", ".join(sorted(missing_columns))
        )

    print("[PASS] Lifecycle history schema verified")

    foreign_keys = conn.execute(
        "PRAGMA foreign_key_list(passport_lifecycle_history)"
    ).fetchall()

    matching_fk = any(
        row[2] == "asset_passports"
        and row[3] == "passport_id"
        and row[4] == "id"
        for row in foreign_keys
    )

    if not matching_fk:
        fail(
            "passport_lifecycle_history.passport_id "
            "foreign key to asset_passports.id not found"
        )

    print("[PASS] Passport foreign key verified")

    passport_count = conn.execute(
        "SELECT COUNT(*) FROM asset_passports"
    ).fetchone()[0]

    history_count = conn.execute(
        "SELECT COUNT(*) FROM passport_lifecycle_history"
    ).fetchone()[0]

    print(f"[INFO] Passport rows preserved: {passport_count}")
    print(f"[INFO] Lifecycle history rows: {history_count}")

    orphan_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM passport_lifecycle_history h
        LEFT JOIN asset_passports p
            ON p.id = h.passport_id
        WHERE p.id IS NULL
        """
    ).fetchone()[0]

    if orphan_count != 0:
        fail(
            f"Lifecycle history orphan references found: {orphan_count}"
        )

    print("[PASS] Lifecycle history orphan check passed")

    violations = conn.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    if violations:
        fail(
            "SQLite foreign-key violations detected: "
            + str(violations)
        )

    print("[PASS] SQLite foreign-key integrity check passed")

    final_tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table'"
        ).fetchall()
    }

    if "passport_lifecycle_history" not in final_tables:
        fail(
            "passport_lifecycle_history table not present "
            "after migration"
        )

    print("[PASS] Migration 003 completed successfully")
    print()
    print("RESULT: MIGRATION 003 PASSED")

finally:
    conn.close()
