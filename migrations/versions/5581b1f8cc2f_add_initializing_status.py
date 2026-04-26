"""add INITIALIZING status

Revision ID: 5581b1f8cc2f
Revises: ab058548b6a2
Create Date: 2026-04-09 11:56:24.565383

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5581b1f8cc2f'
down_revision: Union[str, Sequence[str], None] = 'ab058548b6a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE generation_status_enum ADD VALUE IF NOT EXISTS 'INITIALIZING'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
