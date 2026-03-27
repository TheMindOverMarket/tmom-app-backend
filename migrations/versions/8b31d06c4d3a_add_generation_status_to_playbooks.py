"""add generation_status to playbooks

Revision ID: 8b31d06c4d3a
Revises: f9e7b2a6d1c8
Create Date: 2026-03-26 20:40:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8b31d06c4d3a"
down_revision: Union[str, Sequence[str], None] = "f9e7b2a6d1c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


generation_status_enum = sa.Enum(
    "PENDING",
    "COMPLETED",
    "FAILED",
    name="generation_status_enum",
)


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "PENDING",
            "COMPLETED",
            "FAILED",
            name="generation_status_enum",
        ).create(bind, checkfirst=True)

    with op.batch_alter_table("playbooks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "generation_status",
                generation_status_enum,
                nullable=True,
                server_default="COMPLETED",
            )
        )

    op.execute("UPDATE playbooks SET generation_status = 'COMPLETED' WHERE generation_status IS NULL")

    with op.batch_alter_table("playbooks") as batch_op:
        batch_op.alter_column(
            "generation_status",
            existing_type=generation_status_enum,
            nullable=False,
            server_default="COMPLETED",
        )


def downgrade() -> None:
    bind = op.get_bind()

    with op.batch_alter_table("playbooks") as batch_op:
        batch_op.drop_column("generation_status")

    if bind.dialect.name == "postgresql":
        postgresql.ENUM(
            "PENDING",
            "COMPLETED",
            "FAILED",
            name="generation_status_enum",
        ).drop(bind, checkfirst=True)
