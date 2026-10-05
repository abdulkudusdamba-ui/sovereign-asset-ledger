from datetime import datetime, timezone
from pathlib import Path
import shutil
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "sal.db"


def create_backup() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path = ROOT / f"sal.db.backup-migration-006-{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def fail(message: str):
    raise RuntimeError(message)


def migrate():
    print("===== SAL MIGRATION 006: EVIDENCE REVIEW HISTORY =====")

    if not DB_PATH.exists():
        fail(f"Database not found: {DB_PATH}")

    backup_path = create_backup()
    print(f"[PASS] Database backup created: {backup_path.name}")

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        required_tables = {
            "asset_registry",
            "asset_passports",
            "asset_evidence",
        }

        missing = required_tables - tables

        if missing:
            fail(
                "Required tables missing: "
                + ", ".join(sorted(missing))
            )

        print("[PASS] Required SAL Evidence tables exist")

        evidence_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(asset_evidence)"
            ).fetchall()
        }

        required_evidence_columns = {
            "id",
            "evidence_id",
            "passport_id",
            "evidence_type",
            "title",
            "status",
            "submitted_by",
            "created_at",
        }

        missing_evidence_columns = (
            required_evidence_columns - evidence_columns
        )

        if missing_evidence_columns:
            fail(
                "asset_evidence is missing columns: "
                + ", ".join(sorted(missing_evidence_columns))
            )

        print("[PASS] asset_evidence base schema verified")

        if "version" not in evidence_columns:
            conn.execute(
                """
                ALTER TABLE asset_evidence
                ADD COLUMN version INTEGER NOT NULL DEFAULT 1
                """
            )
            print("[PASS] asset_evidence.version column added")
        else:
            print("[INFO] asset_evidence.version already exists")

        if "asset_evidence_review_history" not in tables:
            conn.execute(
                """
                CREATE TABLE asset_evidence_review_history (
                    id INTEGER PRIMARY KEY,
                    evidence_id INTEGER NOT NULL,
                    from_status VARCHAR NOT NULL,
                    to_status VARCHAR NOT NULL,
                    reason VARCHAR,
                    reference VARCHAR,
                    reviewed_by VARCHAR,
                    created_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (evidence_id)
                        REFERENCES asset_evidence(id)
                )
                """
            )

            print(
                "[PASS] asset_evidence_review_history table created"
            )
        else:
            print(
                "[INFO] asset_evidence_review_history table already exists"
            )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_review_history_id
            ON asset_evidence_review_history(id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_review_history_evidence_id
            ON asset_evidence_review_history(evidence_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS
            ix_asset_evidence_review_history_created_at
            ON asset_evidence_review_history(created_at)
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            uq_asset_evidence_review_history_reference
            ON asset_evidence_review_history(reference)
            WHERE reference IS NOT NULL
            """
        )

        conn.commit()

        print("[PASS] Evidence review history indexes verified")

        history_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(asset_evidence_review_history)"
            ).fetchall()
        }

        expected_history_columns = {
            "id",
            "evidence_id",
            "from_status",
            "to_status",
            "reason",
            "reference",
            "reviewed_by",
            "created_at",
        }

        missing_history_columns = (
            expected_history_columns - history_columns
        )

        if missing_history_columns:
            fail(
                "asset_evidence_review_history is missing columns: "
                + ", ".join(sorted(missing_history_columns))
            )

        print("[PASS] Evidence review history schema verified")

        foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(asset_evidence_review_history)"
        ).fetchall()

        matching_fk = any(
            row[2] == "asset_evidence"
            and row[3] == "evidence_id"
            and row[4] == "id"
            for row in foreign_keys
        )

        if not matching_fk:
            fail(
                "asset_evidence_review_history.evidence_id "
                "foreign key to asset_evidence.id not found"
            )

        print("[PASS] Evidence foreign key verified")

        orphan_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM asset_evidence_review_history AS h
            LEFT JOIN asset_evidence AS e
                ON e.id = h.evidence_id
            WHERE e.id IS NULL
            """
        ).fetchone()[0]

        if orphan_count != 0:
            fail(
                "Evidence review history orphan references found: "
                f"{orphan_count}"
            )

        print("[PASS] Evidence review history orphan check passed")

        duplicate_references = conn.execute(
            """
            SELECT reference, COUNT(*)
            FROM asset_evidence_review_history
            WHERE reference IS NOT NULL
            GROUP BY reference
            HAVING COUNT(*) > 1
            """
        ).fetchall()

        if duplicate_references:
            fail(
                "Duplicate evidence review references found: "
                f"{duplicate_references}"
            )

        print("[PASS] Evidence review references verified")

        invalid_versions = conn.execute(
            """
            SELECT COUNT(*)
            FROM asset_evidence
            WHERE version < 1 OR version IS NULL
            """
        ).fetchone()[0]

        if invalid_versions != 0:
            fail(
                "Invalid Evidence version values found: "
                f"{invalid_versions}"
            )

        print("[PASS] Evidence version values verified")

        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            fail(
                "SQLite foreign-key violations detected: "
                + str(violations)
            )

        print("[PASS] SQLite foreign-key integrity check passed")

        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM asset_evidence"
        ).fetchone()[0]

        history_count = conn.execute(
            "SELECT COUNT(*) FROM asset_evidence_review_history"
        ).fetchone()[0]

        print(f"[INFO] Evidence rows preserved: {evidence_count}")
        print(f"[INFO] Evidence review history rows: {history_count}")

        final_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "asset_evidence_review_history" not in final_tables:
            fail(
                "asset_evidence_review_history table not present "
                "after migration"
            )

        print("[PASS] Migration 006 completed successfully")
        print()
        print("RESULT: MIGRATION 006 READY")

    except Exception:
        conn.rollback()
        print()
        print("MIGRATION 006 FAILED.")
        print("Database transaction rolled back.")
        print(f"Backup remains available at: {backup_path}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
