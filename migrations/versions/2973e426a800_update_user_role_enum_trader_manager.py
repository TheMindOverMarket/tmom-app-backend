"""update user role enum TRADER MANAGER

Revision ID: 2973e426a800
Revises: 0da62ff31693
Create Date: 2026-04-07 22:07:55.539326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2973e426a800'
down_revision: Union[str, Sequence[str], None] = '0da62ff31693'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Commit existing transaction to allow ALTER TYPE ... ADD VALUE
    op.execute("COMMIT")
    op.execute("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'TRADER'")
    op.execute("ALTER TYPE user_role_enum ADD VALUE IF NOT EXISTS 'MANAGER'")
    
    # Update server default for the role column
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('role', server_default='TRADER')


def downgrade() -> None:
    """Downgrade schema."""
    pass
