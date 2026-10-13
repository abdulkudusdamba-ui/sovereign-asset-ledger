"""merge provenance and vehicle verification heads

Revision ID: 5f3cc5b646b1
Revises: 6df34aa21c9b, a3c1d5e7b901
Create Date: 2026-10-13 14:25:29.513974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f3cc5b646b1'
down_revision: Union[str, Sequence[str], None] = ('6df34aa21c9b', 'a3c1d5e7b901')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
