"""add rule metadata columns

Revision ID: 3c0b9d1e4f2a
Revises: 8b31d06c4d3a
Create Date: 2026-03-26 20:55:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c0b9d1e4f2a"
down_revision: Union[str, Sequence[str], None] = "8b31d06c4d3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rules") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("category", sa.String(), nullable=True, server_default="logic")
        )

    op.execute("UPDATE rules SET category = 'logic' WHERE category IS NULL")

    with op.batch_alter_table("rules") as batch_op:
        batch_op.alter_column(
            "category",
            existing_type=sa.String(),
            nullable=False,
            server_default="logic",
        )


def downgrade() -> None:
    with op.batch_alter_table("rules") as batch_op:
        batch_op.drop_column("category")
        batch_op.drop_column("description")
