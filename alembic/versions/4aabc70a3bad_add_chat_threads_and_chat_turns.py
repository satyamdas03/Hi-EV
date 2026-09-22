"""add chat_threads and chat_turns

Revision ID: 4aabc70a3bad
Revises: 3fdf19081353
Create Date: 2026-09-22 09:35:47.916154

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4aabc70a3bad'
down_revision: str | None = '3fdf19081353'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'chat_threads',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'chat_turns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('thread_id', sa.Uuid(), nullable=False),
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tool_name', sa.String(length=64), nullable=True),
        sa.Column('route', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id', 'ordinal', name='uix_chat_turn_thread_ordinal'),
    )
    op.create_index(op.f('ix_chat_turns_thread_id'), 'chat_turns', ['thread_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chat_turns_thread_id'), table_name='chat_turns')
    op.drop_table('chat_turns')
    op.drop_table('chat_threads')
