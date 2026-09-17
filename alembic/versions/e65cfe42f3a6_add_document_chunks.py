"""add document_chunks

Revision ID: e65cfe42f3a6
Revises: aacdc9089a90
Create Date: 2026-09-17 12:22:56.471482

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e65cfe42f3a6'
down_revision: str | None = 'aacdc9089a90'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('source_id', sa.String(length=512), nullable=False),
        sa.Column('project_name', sa.String(length=128), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_id', 'chunk_index', name='uix_document_chunk_source'),
    )
    op.create_index(op.f('ix_document_chunks_project_name'), 'document_chunks', ['project_name'], unique=False)
    op.create_index(op.f('ix_document_chunks_source'), 'document_chunks', ['source'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_chunks_source'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_project_name'), table_name='document_chunks')
    op.drop_table('document_chunks')
