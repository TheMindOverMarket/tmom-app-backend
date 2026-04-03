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
    print(f"[ALEMBIC] Detected dialect: {dialect}")
    
    if dialect == "postgresql":
        print("[ALEMBIC] Running unified PostgreSQL update for symbol field...")
        op.execute(
            """
            UPDATE playbooks
            SET symbol = CASE
                -- 1. If symbol exists and needs slash normalization
                WHEN symbol IS NOT NULL AND symbol <> '' AND strpos(symbol, '/') = 0 
                    THEN upper(replace(symbol, '-', '/')) || '/USD'
                -- 2. If market exists and needs slash normalization
                WHEN market IS NOT NULL AND market <> '' AND strpos(market, '/') = 0
                    THEN upper(replace(market, '-', '/')) || '/USD'
                -- 3. Base case from context
                WHEN context IS NOT NULL AND trim(coalesce(context->>'symbol', '')) <> '' 
                    THEN CASE 
                        WHEN strpos(context->>'symbol', '/') = 0 
                        THEN upper(replace(context->>'symbol', '-', '/')) || '/USD'
                        ELSE upper(replace(context->>'symbol', '-', '/'))
                    END
                ELSE 'BTC/USD'
            END
            """
        )
    else:
        print("[ALEMBIC] Running unified SQLite update for symbol field...")
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

    print("[ALEMBIC] Finalizing symbol column (nullable=False, index=True)...")
    with op.batch_alter_table("playbooks", schema=None) as batch_op:
        batch_op.alter_column("symbol", existing_type=sa.String(), nullable=False)
        batch_op.create_index(batch_op.f("ix_playbooks_symbol"), ["symbol"], unique=False)
    print("[ALEMBIC] Migration b2d6e5f4c1a7 complete.")


def downgrade() -> None:
    with op.batch_alter_table("playbooks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_playbooks_symbol"))
        batch_op.drop_column("symbol")
