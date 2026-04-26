"""force backfill is_audit_ready

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-04-26 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, Sequence[str], None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Force update all existing COMPLETED sessions to be audit-ready
    op.execute("UPDATE sessions SET is_audit_ready = true WHERE status = 'COMPLETED'")


def downgrade() -> None:
    pass
