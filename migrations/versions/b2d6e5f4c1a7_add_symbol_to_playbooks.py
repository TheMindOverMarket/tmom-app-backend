"""add symbol to playbooks

Revision ID: b2d6e5f4c1a7
Revises: 4b6f5f1f8a2e
Create Date: 2026-04-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2d6e5f4c1a7"
down_revision: Union[str, Sequence[str], None] = "4b6f5f1f8a2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("playbooks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("symbol", sa.String(), nullable=True))

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            UPDATE playbooks
            SET symbol = CASE
                WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                WHEN context IS NOT NULL AND trim(coalesce(context->>'symbol', '')) <> '' THEN upper(replace(context->>'symbol', '-', '/'))
                ELSE 'BTC/USD'
            END
            """
        )
    else:
        op.execute(
            """
            UPDATE playbooks
            SET symbol = CASE
                WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                WHEN context IS NOT NULL
                     AND json_extract(context, '$.symbol') IS NOT NULL
                     AND trim(json_extract(context, '$.symbol')) <> ''
                THEN upper(replace(json_extract(context, '$.symbol'), '-', '/'))
                ELSE 'BTC/USD'
            END
            """
        )

    op.execute(
        """
        UPDATE playbooks
        SET symbol = symbol || '/USD'
        WHERE instr(symbol, '/') = 0
        """
    )

    with op.batch_alter_table("playbooks", schema=None) as batch_op:
        batch_op.alter_column("symbol", existing_type=sa.String(), nullable=False)
        batch_op.create_index(batch_op.f("ix_playbooks_symbol"), ["symbol"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("playbooks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_playbooks_symbol"))
        batch_op.drop_column("symbol")
