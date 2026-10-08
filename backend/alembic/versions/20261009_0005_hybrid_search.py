"""Hybrid search: GIN index for PostgreSQL full-text search (FR-24).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expression GIN index on to_tsvector('english', text) for fast full-text matching
    op.execute("CREATE INDEX idx_chunks_fts ON chunks USING gin (to_tsvector('english', text));")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts;")
