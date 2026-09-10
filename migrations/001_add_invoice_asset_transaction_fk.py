from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone


DATABASE_PATH = Path("sal.db")


def backup_database() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    backup_path = DATABASE_PATH.with_name(
        f"sal.db.backup-migration-001-{timestamp}.db"
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

        print("\n========== MIGRATION 001 ==========\n")
        print("Adding invoices.asset_transaction_id")

        # -------------------------------------------------
        # 1. Confirm required tables exist
        # -------------------------------------------------

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
            "invoices",
            "asset_transactions",
        }

        missing_tables = required_tables - tables

        if missing_tables:
            raise RuntimeError(
                f"Required tables are missing: {sorted(missing_tables)}"
            )

        # -------------------------------------------------
        # 2. Inspect invoices schema
        # -------------------------------------------------

        columns = cursor.execute(
            "PRAGMA table_info(invoices)"
        ).fetchall()

        column_names = {column[1] for column in columns}

        # -------------------------------------------------
        # 3. Add relationship column if necessary
        # -------------------------------------------------

        if "asset_transaction_id" in column_names:
            print(
                "asset_transaction_id already exists."
            )
        else:
            cursor.execute(
                """
                ALTER TABLE invoices
                ADD COLUMN asset_transaction_id INTEGER
                """
            )

            print(
                "asset_transaction_id column added."
            )

        # -------------------------------------------------
        # 4. Backfill existing ASSET_TRANSACTION invoices
        # -------------------------------------------------

        rows = cursor.execute(
            """
            SELECT id, service
            FROM invoices
            WHERE service LIKE 'ASSET_TRANSACTION:%'
            ORDER BY id
            """
        ).fetchall()

        print(
            f"Found {len(rows)} ASSET_TRANSACTION invoice(s)."
        )

        for invoice_id, service in rows:

            if not service:
                continue

            reference = service.split(":", 1)[1].strip()

            try:
                transaction_id = int(reference)
            except (TypeError, ValueError):
                raise RuntimeError(
                    f"Invoice {invoice_id} contains an invalid "
                    f"asset transaction reference: {service}"
                )

            transaction = cursor.execute(
                """
                SELECT id
                FROM asset_transactions
                WHERE id = ?
                """,
                (transaction_id,),
            ).fetchone()

            if not transaction:
                raise RuntimeError(
                    f"Invoice {invoice_id} references missing "
                    f"AssetTransaction {transaction_id}"
                )

            cursor.execute(
                """
                UPDATE invoices
                SET asset_transaction_id = ?
                WHERE id = ?
                """,
                (transaction_id, invoice_id),
            )

            print(
                f"Invoice {invoice_id} "
                f"-> AssetTransaction {transaction_id}"
            )

        # -------------------------------------------------
        # 5. Verify every populated relationship
        # -------------------------------------------------

        invalid_references = cursor.execute(
            """
            SELECT
                i.id,
                i.asset_transaction_id
            FROM invoices AS i
            LEFT JOIN asset_transactions AS a
                ON a.id = i.asset_transaction_id
            WHERE i.asset_transaction_id IS NOT NULL
              AND a.id IS NULL
            """
        ).fetchall()

        if invalid_references:
            raise RuntimeError(
                "Invalid asset transaction references found: "
                f"{invalid_references}"
            )

        # -------------------------------------------------
        # 6. Verify ASSET_TRANSACTION service references
        # -------------------------------------------------

        mismatches = cursor.execute(
            """
            SELECT
                id,
                service,
                asset_transaction_id
            FROM invoices
            WHERE service LIKE 'ASSET_TRANSACTION:%'
              AND asset_transaction_id !=
                  CAST(substr(service, 19) AS INTEGER)
            """
        ).fetchall()

        if mismatches:
            raise RuntimeError(
                "Service/reference mismatches found: "
                f"{mismatches}"
            )

        # -------------------------------------------------
        # 7. Verify invoice count
        # -------------------------------------------------

        invoice_count = cursor.execute(
            "SELECT COUNT(*) FROM invoices"
        ).fetchone()[0]

        # -------------------------------------------------
        # 8. Commit
        # -------------------------------------------------

        connection.commit()

        print("\n========== MIGRATION 001 PASSED ==========\n")
        print(
            f"Invoice rows preserved: {invoice_count}"
        )
        print(
            "asset_transaction_id relationships verified."
        )

    except Exception:
        connection.rollback()

        print("\nMIGRATION 001 FAILED.")
        print("Database transaction rolled back.")

        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
