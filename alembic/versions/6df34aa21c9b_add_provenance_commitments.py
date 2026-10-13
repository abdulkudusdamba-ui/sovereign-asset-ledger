"""add SAL provenance commitments and anchor attempts

Revision ID: 6df34aa21c9b
Revises: 1238c49a846b
Create Date: 2026-10-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6df34aa21c9b"
down_revision: Union[str, Sequence[str], None] = "1238c49a846b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provenance_commitments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commitment_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("asset_registry_id", sa.Integer(), nullable=True),
        sa.Column("passport_id", sa.Integer(), nullable=True),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("previous_commitment_id", sa.String(), nullable=True),
        sa.Column("commitment_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(), nullable=True),
        sa.Column("signer_key_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ledger_provider", sa.String(), nullable=False),
        sa.Column("network_id", sa.String(), nullable=False),
        sa.Column(
            "anchor_status",
            sa.String(),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("anchor_reference", sa.String(), nullable=True),
        sa.Column(
            "anchor_attempts",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_anchor_error", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["asset_registry_id"],
            ["asset_registry.id"],
        ),
        sa.ForeignKeyConstraint(["event_id"], ["audit_events.event_id"]),
        sa.ForeignKeyConstraint(["passport_id"], ["asset_passports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commitment_id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(
        "ix_provenance_commitments_commitment_id",
        "provenance_commitments",
        ["commitment_id"],
    )
    op.create_index(
        "ix_provenance_commitments_event_id",
        "provenance_commitments",
        ["event_id"],
    )
    op.create_index(
        "ix_provenance_commitments_asset_registry_id",
        "provenance_commitments",
        ["asset_registry_id"],
    )
    op.create_index(
        "ix_provenance_commitments_passport_id",
        "provenance_commitments",
        ["passport_id"],
    )

    op.create_table(
        "provenance_anchor_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("commitment_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("anchor_reference", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["commitment_id"],
            ["provenance_commitments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provenance_anchor_attempts_commitment_id",
        "provenance_anchor_attempts",
        ["commitment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_provenance_anchor_attempts_commitment_id",
        table_name="provenance_anchor_attempts",
    )
    op.drop_table("provenance_anchor_attempts")
    op.drop_index(
        "ix_provenance_commitments_passport_id",
        table_name="provenance_commitments",
    )
    op.drop_index(
        "ix_provenance_commitments_asset_registry_id",
        table_name="provenance_commitments",
    )
    op.drop_index(
        "ix_provenance_commitments_event_id",
        table_name="provenance_commitments",
    )
    op.drop_index(
        "ix_provenance_commitments_commitment_id",
        table_name="provenance_commitments",
    )
    op.drop_table("provenance_commitments")
