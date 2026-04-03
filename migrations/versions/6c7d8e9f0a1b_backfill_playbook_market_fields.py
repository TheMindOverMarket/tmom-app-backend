"""backfill playbook market fields

Revision ID: 6c7d8e9f0a1b
Revises: b2d6e5f4c1a7
Create Date: 2026-04-03 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6c7d8e9f0a1b"
down_revision: Union[str, Sequence[str], None] = "b2d6e5f4c1a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            """
            UPDATE playbooks
            SET
                symbol = CASE
                    WHEN symbol IS NOT NULL AND trim(symbol) <> '' THEN upper(replace(symbol, '-', '/'))
                    WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                    WHEN context IS NOT NULL AND trim(coalesce(context->>'symbol', '')) <> '' THEN upper(replace(context->>'symbol', '-', '/'))
                    WHEN context IS NOT NULL AND trim(coalesce(context->>'market', '')) <> '' THEN upper(replace(context->>'market', '-', '/'))
                    ELSE 'BTC/USD'
                END,
                market = CASE
                    WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                    WHEN symbol IS NOT NULL AND trim(symbol) <> '' THEN upper(replace(symbol, '-', '/'))
                    WHEN context IS NOT NULL AND trim(coalesce(context->>'market', '')) <> '' THEN upper(replace(context->>'market', '-', '/'))
                    WHEN context IS NOT NULL AND trim(coalesce(context->>'symbol', '')) <> '' THEN upper(replace(context->>'symbol', '-', '/'))
                    ELSE 'BTC/USD'
                END
            """
        )

        op.execute(
            """
            UPDATE playbooks
            SET
                symbol = CASE WHEN position('/' in symbol) = 0 THEN symbol || '/USD' ELSE symbol END,
                market = CASE WHEN position('/' in market) = 0 THEN market || '/USD' ELSE market END
            WHERE symbol IS NOT NULL OR market IS NOT NULL
            """
        )

        op.execute(
            """
            UPDATE playbooks
            SET context = jsonb_set(
                jsonb_set(
                    COALESCE(context, '{}'::jsonb),
                    '{symbol}',
                    to_jsonb(symbol),
                    true
                ),
                '{market}',
                to_jsonb(market),
                true
            )
            WHERE
                symbol IS NOT NULL
                AND market IS NOT NULL
                AND (
                    context IS NULL
                    OR trim(coalesce(context->>'symbol', '')) = ''
                    OR trim(coalesce(context->>'market', '')) = ''
                    OR upper(replace(coalesce(context->>'symbol', ''), '-', '/')) <> symbol
                    OR upper(replace(coalesce(context->>'market', ''), '-', '/')) <> market
                )
            """
        )
    else:
        op.execute(
            """
            UPDATE playbooks
            SET
                symbol = CASE
                    WHEN symbol IS NOT NULL AND trim(symbol) <> '' THEN upper(replace(symbol, '-', '/'))
                    WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                    WHEN context IS NOT NULL
                         AND json_extract(context, '$.symbol') IS NOT NULL
                         AND trim(json_extract(context, '$.symbol')) <> ''
                    THEN upper(replace(json_extract(context, '$.symbol'), '-', '/'))
                    WHEN context IS NOT NULL
                         AND json_extract(context, '$.market') IS NOT NULL
                         AND trim(json_extract(context, '$.market')) <> ''
                    THEN upper(replace(json_extract(context, '$.market'), '-', '/'))
                    ELSE 'BTC/USD'
                END,
                market = CASE
                    WHEN market IS NOT NULL AND trim(market) <> '' THEN upper(replace(market, '-', '/'))
                    WHEN symbol IS NOT NULL AND trim(symbol) <> '' THEN upper(replace(symbol, '-', '/'))
                    WHEN context IS NOT NULL
                         AND json_extract(context, '$.market') IS NOT NULL
                         AND trim(json_extract(context, '$.market')) <> ''
                    THEN upper(replace(json_extract(context, '$.market'), '-', '/'))
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
            SET
                symbol = CASE WHEN instr(symbol, '/') = 0 THEN symbol || '/USD' ELSE symbol END,
                market = CASE WHEN instr(market, '/') = 0 THEN market || '/USD' ELSE market END
            WHERE symbol IS NOT NULL OR market IS NOT NULL
            """
        )

        op.execute(
            """
            UPDATE playbooks
            SET context = json_set(
                json_set(
                    COALESCE(context, '{}'),
                    '$.symbol',
                    json_quote(symbol)
                ),
                '$.market',
                json_quote(market)
            )
            WHERE symbol IS NOT NULL AND market IS NOT NULL
            """
        )


def downgrade() -> None:
    # One-time data repair migration. No downgrade.
    pass
