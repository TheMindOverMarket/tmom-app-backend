"""add is_audit_ready to session

Revision ID: 1a2b3c4d5e6f
Revises: 88441d70a650
Create Date: 2026-04-26 14:41:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, Sequence[str], None] = '88441d70a650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_audit_ready column to sessions table
    op.add_column('sessions', sa.Column('is_audit_ready', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    # Remove is_audit_ready column from sessions table
    op.drop_column('sessions', 'is_audit_ready')
