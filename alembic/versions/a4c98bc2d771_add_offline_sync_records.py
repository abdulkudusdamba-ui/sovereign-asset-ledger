"""Add Offline SAL synchronization records.

Revision ID: a4c98bc2d771
Revises: 1238c49a846b
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4c98bc2d771"
down_revision: Union[str, Sequence[str], None] = "1238c49a846b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_registry",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    op.create_table(
        "offline_sync_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("asset_registry_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["asset_registry_id"], ["asset_registry.id"]),
        sa.UniqueConstraint("operation_id"),
    )
    op.create_index(
        "ix_offline_sync_operations_operation_id",
        "offline_sync_operations",
        ["operation_id"],
    )
    op.create_index(
        "ix_offline_sync_operations_actor_id",
        "offline_sync_operations",
        ["actor_id"],
    )
    op.create_index(
        "ix_offline_sync_operations_asset_registry_id",
        "offline_sync_operations",
        ["asset_registry_id"],
    )

    op.create_table(
        "offline_sync_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_record_id", sa.Integer(), nullable=True),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("submitted_by", sa.Integer(), nullable=False),
        sa.Column("submission_payload", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("resolution", sa.String(length=16), nullable=True),
        sa.Column("resolution_note", sa.String(length=1000), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["operation_record_id"],
            ["offline_sync_operations.id"],
        ),
    )
    op.create_index(
        "ix_offline_sync_conflicts_operation_record_id",
        "offline_sync_conflicts",
        ["operation_record_id"],
    )
    op.create_index(
        "ix_offline_sync_conflicts_operation_id",
        "offline_sync_conflicts",
        ["operation_id"],
    )
    op.create_index(
        "ix_offline_sync_conflicts_submitted_by",
        "offline_sync_conflicts",
        ["submitted_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_offline_sync_conflicts_submitted_by",
        table_name="offline_sync_conflicts",
    )
    op.drop_index(
        "ix_offline_sync_conflicts_operation_id",
        table_name="offline_sync_conflicts",
    )
    op.drop_index(
        "ix_offline_sync_conflicts_operation_record_id",
        table_name="offline_sync_conflicts",
    )
    op.drop_table("offline_sync_conflicts")
    op.drop_index(
        "ix_offline_sync_operations_asset_registry_id",
        table_name="offline_sync_operations",
    )
    op.drop_index(
        "ix_offline_sync_operations_actor_id",
        table_name="offline_sync_operations",
    )
    op.drop_index(
        "ix_offline_sync_operations_operation_id",
        table_name="offline_sync_operations",
    )
    op.drop_table("offline_sync_operations")
    op.drop_column("asset_registry", "version")
