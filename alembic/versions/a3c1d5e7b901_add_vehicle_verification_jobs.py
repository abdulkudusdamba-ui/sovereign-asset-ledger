"""Add vehicle verification jobs

Revision ID: a3c1d5e7b901
Revises: 1238c49a846b
Create Date: 2026-10-13 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3c1d5e7b901"
down_revision: Union[str, Sequence[str], None] = "1238c49a846b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE = "status IN ('PENDING', 'IN_PROGRESS')"


def upgrade() -> None:
    """Create the vehicle_verification_jobs table (additive only)."""
    op.create_table(
        "vehicle_verification_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("asset_registry_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("mismatched_fields", sa.String(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')",
            name="ck_vehicle_verification_jobs_status",
        ),
        sa.ForeignKeyConstraint(["asset_registry_id"], ["asset_registry.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_vehicle_verification_jobs_user_key",
        ),
    )
    op.create_index(
        "ix_vehicle_verification_jobs_id",
        "vehicle_verification_jobs",
        ["id"],
    )
    op.create_index(
        "ix_vehicle_verification_jobs_job_id",
        "vehicle_verification_jobs",
        ["job_id"],
        unique=True,
    )
    op.create_index(
        "ix_vehicle_verification_jobs_asset_registry_id",
        "vehicle_verification_jobs",
        ["asset_registry_id"],
    )
    op.create_index(
        "uq_vehicle_verification_jobs_one_active",
        "vehicle_verification_jobs",
        ["asset_registry_id", "provider"],
        unique=True,
        postgresql_where=sa.text(ACTIVE),
    )


def downgrade() -> None:
    """Drop the vehicle_verification_jobs table."""
    op.drop_index(
        "uq_vehicle_verification_jobs_one_active",
        table_name="vehicle_verification_jobs",
    )
    op.drop_index(
        "ix_vehicle_verification_jobs_asset_registry_id",
        table_name="vehicle_verification_jobs",
    )
    op.drop_index(
        "ix_vehicle_verification_jobs_job_id",
        table_name="vehicle_verification_jobs",
    )
    op.drop_index(
        "ix_vehicle_verification_jobs_id",
        table_name="vehicle_verification_jobs",
    )
    op.drop_table("vehicle_verification_jobs")
