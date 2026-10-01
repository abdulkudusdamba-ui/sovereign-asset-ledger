from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone


DATABASE_PATH = Path("sal.db")


def backup_database() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    backup_path = DATABASE_PATH.with_name(
        f"sal.db.backup-migration-002-{timestamp}.db"
    )

    shutil.copy2(DATABASE_PATH, backup_path)

    print(f"Database backup created: {backup_path}")

    return backup_path


def migrate():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    backup_database()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        print("\n========== MIGRATION 002 ==========\n")
        print("Creating asset_passports table")

        tables = {
            row[0]
            for row in cursor.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        required_tables = {
            "asset_registry"
        }

        missing_tables = required_tables - tables

        if missing_tables:
            raise RuntimeError(
                f"Required tables are missing: {sorted(missing_tables)}"
            )

        if "asset_passports" in tables:
            print("asset_passports table already exists.")
        else:
            cursor.execute(
                """
                CREATE TABLE asset_passports (
                    id INTEGER PRIMARY KEY,
                    passport_id VARCHAR NOT NULL UNIQUE,
                    asset_registry_id INTEGER NOT NULL UNIQUE,
                    status VARCHAR NOT NULL DEFAULT 'ACTIVE',
                    lifecycle_state VARCHAR NOT NULL DEFAULT 'REGISTERED',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(asset_registry_id)
                        REFERENCES asset_registry(id)
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX ix_asset_passports_id
                ON asset_passports(id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX ix_asset_passports_passport_id
                ON asset_passports(passport_id)
                """
            )

            cursor.execute(
                """
                CREATE INDEX ix_asset_passports_asset_registry_id
                ON asset_passports(asset_registry_id)
                """
            )

            print("asset_passports table created.")

        # -------------------------------------------------
        # Verify Passport table
        # -------------------------------------------------

        columns = cursor.execute(
            "PRAGMA table_info(asset_passports)"
        ).fetchall()

        column_names = {column[1] for column in columns}

        required_columns = {
            "id",
            "passport_id",
            "asset_registry_id",
            "status",
            "lifecycle_state",
            "created_at",
            "updated_at",
        }

        missing_columns = required_columns - column_names

        if missing_columns:
            raise RuntimeError(
                f"Passport table is missing columns: {sorted(missing_columns)}"
            )

        # -------------------------------------------------
        # Verify one-to-one uniqueness
        # -------------------------------------------------

        duplicate_registry_links = cursor.execute(
            """
            SELECT asset_registry_id, COUNT(*)
            FROM asset_passports
            GROUP BY asset_registry_id
            HAVING COUNT(*) > 1
            """
        ).fetchall()

        if duplicate_registry_links:
            raise RuntimeError(
                "Duplicate asset_registry_id Passport relationships found: "
                f"{duplicate_registry_links}"
            )

        # -------------------------------------------------
        # Verify foreign-key references
        # -------------------------------------------------

        invalid_references = cursor.execute(
            """
            SELECT
                p.id,
                p.asset_registry_id
            FROM asset_passports AS p
            LEFT JOIN asset_registry AS a
                ON a.id = p.asset_registry_id
            WHERE a.id IS NULL
            """
        ).fetchall()

        if invalid_references:
            raise RuntimeError(
                "Invalid Passport -> AssetRegistry references found: "
                f"{invalid_references}"
            )

        passport_count = cursor.execute(
            "SELECT COUNT(*) FROM asset_passports"
        ).fetchone()[0]

        registry_count = cursor.execute(
            "SELECT COUNT(*) FROM asset_registry"
        ).fetchone()[0]

        connection.commit()

        print("\n========== MIGRATION 002 PASSED ==========\n")
        print(f"Asset Registry rows preserved: {registry_count}")
        print(f"Passport rows: {passport_count}")
        print("Passport schema verified.")
        print("One-to-one relationship verified.")
        print("Foreign-key references verified.")

    except Exception:
        connection.rollback()

        print("\nMIGRATION 002 FAILED.")
        print("Database transaction rolled back.")

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
