"""merge playbook and user role heads

Revision ID: 7d8e9f0a1b2c
Revises: 6bf7f68619f9, 6c7d8e9f0a1b
Create Date: 2026-04-03 19:05:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "7d8e9f0a1b2c"
down_revision: Union[str, Sequence[str], None] = ("6bf7f68619f9", "6c7d8e9f0a1b")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
