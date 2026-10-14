"""Add offline sync operations and reviewable conflicts.

Revision ID: 9d3a1f2c7b40
Revises: 1238c49a846b
Create Date: 2026-10-14 06:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d3a1f2c7b40"
down_revision: Union[str, Sequence[str], None] = "1238c49a846b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offline_sync_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("request_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result_payload", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_id",
            "operation_id",
            name="uq_offline_operation_actor_id",
        ),
    )
    op.create_index(
        "ix_offline_sync_operations_actor_created",
        "offline_sync_operations",
        ["actor_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "offline_sync_conflicts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("operation_record_id", sa.Integer(), nullable=False),
        sa.Column("submission_hash", sa.String(length=64), nullable=False),
        sa.Column("conflict_type", sa.String(length=50), nullable=False),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("identifier_type", sa.String(length=50), nullable=True),
        sa.Column("identifier_value", sa.String(length=200), nullable=True),
        sa.Column("submitted_payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolution", sa.String(length=40), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["operation_record_id"], ["offline_sync_operations.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operation_record_id",
            "submission_hash",
            name="uq_offline_conflict_submission",
        ),
    )
    op.create_index(
        "ix_offline_sync_conflicts_status_created",
        "offline_sync_conflicts",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_offline_sync_conflicts_status_created",
        table_name="offline_sync_conflicts",
    )
    op.drop_table("offline_sync_conflicts")
    op.drop_index(
        "ix_offline_sync_operations_actor_created",
        table_name="offline_sync_operations",
    )
    op.drop_table("offline_sync_operations")
