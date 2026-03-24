"""add session and events

Revision ID: f9e7b2a6d1c8
Revises: 3a7906b95505
Create Date: 2026-03-24 16:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f9e7b2a6d1c8'
down_revision: Union[str, Sequence[str], None] = '3a7906b95505'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Handle Enums for Postgres
    # We use sa.Enum with name to handle both Postgres and SQLite (SQLite ignores Enum types)
    # But for Postgres, we can explicitly create the type if needed.
    
    op.create_table('sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('playbook_id', sa.Uuid(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('STARTED', 'COMPLETED', 'FAILED', name='session_status_enum'), server_default='STARTED', nullable=False),
        sa.Column('session_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['playbook_id'], ['playbooks.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessions_id'), 'sessions', ['id'], unique=False)
    op.create_index(op.f('ix_sessions_playbook_id'), 'sessions', ['playbook_id'], unique=False)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)

    op.create_table('session_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.Enum('ADHERENCE', 'DEVIATION', 'NOTIFICATION', 'TRADING', 'SYSTEM', name='session_event_type_enum'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('tick', sa.Integer(), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_events_id'), 'session_events', ['id'], unique=False)
    op.create_index(op.f('ix_session_events_session_id'), 'session_events', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_session_events_session_id'), table_name='session_events')
    op.drop_index(op.f('ix_session_events_id'), table_name='session_events')
    op.drop_table('session_events')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_playbook_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_id'), table_name='sessions')
    op.drop_table('sessions')

    # Note: Enum types persist in Postgres unless dropped explicitly via postgresql.ENUM(...).drop()
    # But for a simple backend migration, this is usually acceptable unless you are in a high-churn env.
