from datetime import datetime

from sqlalchemy import inspect, text

from app.database.database import engine


MIGRATION_NAME = "008_make_audit_events_immutable"


def run():
    print(f"===== SAL MIGRATION 008: {MIGRATION_NAME.upper()} =====")

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "audit_events" not in tables:
        raise RuntimeError(
            "Migration aborted: audit_events table does not exist."
        )

    print("[PASS] audit_events table exists")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"sal.db.backup-migration-008-{timestamp}.db"

    with engine.begin() as conn:
        conn.execute(
            text("VACUUM INTO :backup_path"),
            {"backup_path": backup_path},
        )

    print(f"[PASS] Database backup created: {backup_path}")

    with engine.begin() as conn:
        conn.execute(
            text(
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
        )

        print("[PASS] Audit UPDATE protection trigger created")

        conn.execute(
            text(
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
        )

        print("[PASS] Audit DELETE protection trigger created")

    with engine.connect() as conn:
        trigger_rows = conn.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                  AND name IN (
                      'trg_audit_events_prevent_update',
                      'trg_audit_events_prevent_delete'
                  )
                ORDER BY name
                """
            )
        ).fetchall()

        trigger_names = {
            row[0]
            for row in trigger_rows
        }

        expected_triggers = {
            "trg_audit_events_prevent_update",
            "trg_audit_events_prevent_delete",
        }

        if trigger_names != expected_triggers:
            raise RuntimeError(
                "Audit immutability trigger verification failed. "
                f"Expected {sorted(expected_triggers)}, "
                f"found {sorted(trigger_names)}"
            )

        print("[PASS] Audit immutability triggers verified")

        audit_count = conn.execute(
            text("SELECT COUNT(*) FROM audit_events")
        ).scalar_one()

        print(f"[INFO] Existing audit event rows preserved: {audit_count}")

        fk_errors = conn.execute(
            text("PRAGMA foreign_key_check")
        ).fetchall()

        if fk_errors:
            raise RuntimeError(
                "SQLite foreign-key integrity check failed: "
                + str(fk_errors)
            )

        print("[PASS] SQLite foreign-key integrity check passed")

    print("[PASS] Migration 008 completed successfully")
    print("RESULT: MIGRATION 008 READY")


if __name__ == "__main__":
    run()
