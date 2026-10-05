from datetime import datetime

from sqlalchemy import text
from app.database.database import engine


MIGRATION_NAME = "007_create_audit_events"


def run():
    print("===== SAL MIGRATION 007: GENERAL AUDIT TRAIL =====")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = f"sal.db.backup-migration-007-{timestamp}.db"

    with engine.begin() as conn:
        # ---------------------------------------------------------
        # 1. Verify required tables exist
        # ---------------------------------------------------------
        required_tables = [
            "asset_registry",
            "asset_passports",
        ]

        for table in required_tables:
            exists = conn.execute(
                text(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name = :table_name
                    """
                ),
                {"table_name": table},
            ).scalar()

            if not exists:
                raise RuntimeError(
                    f"Migration aborted: required table '{table}' does not exist."
                )

        print("[PASS] Required SAL dependency tables exist")

        # ---------------------------------------------------------
        # 2. Create database backup
        # ---------------------------------------------------------
        conn.execute(
            text(
                f"VACUUM INTO '{backup_path}'"
            )
        )

        print(f"[PASS] Database backup created: {backup_path}")

        # ---------------------------------------------------------
        # 3. Refuse to silently modify an existing audit table
        # ---------------------------------------------------------
        audit_table_exists = conn.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'audit_events'
                """
            )
        ).scalar()

        if audit_table_exists:
            raise RuntimeError(
                "Migration aborted: audit_events table already exists. "
                "Migration 007 will not modify an existing audit table."
            )

        print("[PASS] audit_events does not already exist")

        # ---------------------------------------------------------
        # 4. Create immutable audit event storage
        # ---------------------------------------------------------
        conn.execute(
            text(
                """
                CREATE TABLE audit_events (
                    id INTEGER PRIMARY KEY,

                    event_id VARCHAR NOT NULL UNIQUE,

                    actor_id INTEGER,
                    actor_type VARCHAR NOT NULL,

                    action VARCHAR NOT NULL,

                    entity_type VARCHAR NOT NULL,
                    entity_id VARCHAR NOT NULL,

                    asset_registry_id INTEGER,
                    passport_id INTEGER,

                    occurred_at DATETIME NOT NULL,
                    received_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    source VARCHAR NOT NULL,

                    device_id VARCHAR,

                    ip_address VARCHAR,
                    user_agent VARCHAR,

                    reason VARCHAR,
                    reference VARCHAR,

                    result VARCHAR NOT NULL,

                    before_data TEXT,
                    after_data TEXT,
                    metadata TEXT,

                    created_at DATETIME NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (asset_registry_id)
                        REFERENCES asset_registry(id),

                    FOREIGN KEY (passport_id)
                        REFERENCES asset_passports(id)
                )
                """
            )
        )

        print("[PASS] audit_events table created")

        # ---------------------------------------------------------
        # 5. Create indexes for audit retrieval
        # ---------------------------------------------------------
        indexes = [
            """
            CREATE INDEX ix_audit_events_event_id
            ON audit_events(event_id)
            """,
            """
            CREATE INDEX ix_audit_events_actor_id
            ON audit_events(actor_id)
            """,
            """
            CREATE INDEX ix_audit_events_action
            ON audit_events(action)
            """,
            """
            CREATE INDEX ix_audit_events_entity
            ON audit_events(entity_type, entity_id)
            """,
            """
            CREATE INDEX ix_audit_events_asset_registry_id
            ON audit_events(asset_registry_id)
            """,
            """
            CREATE INDEX ix_audit_events_passport_id
            ON audit_events(passport_id)
            """,
            """
            CREATE INDEX ix_audit_events_occurred_at
            ON audit_events(occurred_at)
            """,
            """
            CREATE INDEX ix_audit_events_received_at
            ON audit_events(received_at)
            """,
            """
            CREATE INDEX ix_audit_events_reference
            ON audit_events(reference)
            """,
        ]

        for statement in indexes:
            conn.execute(text(statement))

        print("[PASS] Audit Trail indexes created")

        # ---------------------------------------------------------
        # 6. Verify foreign keys
        # ---------------------------------------------------------
        foreign_keys = conn.execute(
            text(
                """
                PRAGMA foreign_key_list(audit_events)
                """
            )
        ).fetchall()

        fk_targets = {
            (row[2], row[4])
            for row in foreign_keys
        }

        expected_fks = {
            ("asset_registry", "id"),
            ("asset_passports", "id"),
        }

        if not expected_fks.issubset(fk_targets):
            raise RuntimeError(
                "Migration verification failed: expected Audit Trail "
                "foreign keys were not created correctly."
            )

        print("[PASS] Audit Trail foreign keys verified")

        # ---------------------------------------------------------
        # 7. Verify schema
        # ---------------------------------------------------------
        columns = {
            row[1]
            for row in conn.execute(
                text("PRAGMA table_info(audit_events)")
            ).fetchall()
        }

        required_columns = {
            "id",
            "event_id",
            "actor_id",
            "actor_type",
            "action",
            "entity_type",
            "entity_id",
            "asset_registry_id",
            "passport_id",
            "occurred_at",
            "received_at",
            "source",
            "device_id",
            "ip_address",
            "user_agent",
            "reason",
            "reference",
            "result",
            "before_data",
            "after_data",
            "metadata",
            "created_at",
        }

        missing_columns = required_columns - columns

        if missing_columns:
            raise RuntimeError(
                "Migration verification failed. Missing columns: "
                + ", ".join(sorted(missing_columns))
            )

        print("[PASS] Audit Trail schema verified")

        # ---------------------------------------------------------
        # 8. Verify indexes
        # ---------------------------------------------------------
        index_rows = conn.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                  AND tbl_name = 'audit_events'
                """
            )
        ).fetchall()

        index_names = {row[0] for row in index_rows}

        expected_indexes = {
            "ix_audit_events_event_id",
            "ix_audit_events_actor_id",
            "ix_audit_events_action",
            "ix_audit_events_entity",
            "ix_audit_events_asset_registry_id",
            "ix_audit_events_passport_id",
            "ix_audit_events_occurred_at",
            "ix_audit_events_received_at",
            "ix_audit_events_reference",
        }

        missing_indexes = expected_indexes - index_names

        if missing_indexes:
            raise RuntimeError(
                "Migration verification failed. Missing indexes: "
                + ", ".join(sorted(missing_indexes))
            )

        print("[PASS] Audit Trail indexes verified")

        # ---------------------------------------------------------
        # 9. Verify SQLite foreign-key integrity
        # ---------------------------------------------------------
        fk_check = conn.execute(
            text("PRAGMA foreign_key_check")
        ).fetchall()

        if fk_check:
            raise RuntimeError(
                "Migration verification failed: SQLite foreign-key "
                "integrity check returned violations."
            )

        print("[PASS] SQLite foreign-key integrity check passed")

        # ---------------------------------------------------------
        # 10. Verify empty initial state
        # ---------------------------------------------------------
        audit_count = conn.execute(
            text("SELECT COUNT(*) FROM audit_events")
        ).scalar()

        print(f"[INFO] Audit event rows: {audit_count}")

        print("[PASS] Migration 007 completed successfully")
        print("RESULT: MIGRATION 007 READY")


if __name__ == "__main__":
    run()
