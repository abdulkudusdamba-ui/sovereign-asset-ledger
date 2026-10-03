from sqlalchemy import text
from app.database.database import engine

MIGRATION_NAME = "005_unique_passport_lifecycle_reference"


def run():
    with engine.begin() as conn:
        duplicate_rows = conn.execute(
            text("""
                SELECT reference, COUNT(*) AS reference_count
                FROM passport_lifecycle_history
                WHERE reference IS NOT NULL
                GROUP BY reference
                HAVING COUNT(*) > 1
            """)
        ).fetchall()

        if duplicate_rows:
            raise RuntimeError(
                "Migration aborted: duplicate non-null lifecycle references exist: "
                + ", ".join(
                    f"{row[0]} ({row[1]})"
                    for row in duplicate_rows
                )
            )

        conn.execute(
            text("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                uq_passport_lifecycle_history_reference
                ON passport_lifecycle_history(reference)
                WHERE reference IS NOT NULL
            """)
        )

        print("Migration 005: unique lifecycle reference index created.")


if __name__ == "__main__":
    run()
