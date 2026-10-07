"""Add vehicle chassis number

Revision ID: 1238c49a846b
Revises: 60609e51049c
Create Date: 2026-10-07 10:33:33.300260

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1238c49a846b"
down_revision: Union[str, Sequence[str], None] = "60609e51049c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable chassis number to vehicles."""
    op.add_column(
        "vehicles",
        sa.Column("chassis_number", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Remove vehicle chassis number."""
    op.drop_column("vehicles", "chassis_number")
