"""Stored tsvector column for BM25 search; replaces the expression index from 0005 (FR-24).

The 0005 expression index could filter rows, but ranking still recomputed ``to_tsvector`` for every
matching chunk (measured: 636 ms for one query on the 1,654-chunk eval corpus). A stored generated
column is computed once per chunk at insert time.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_chunks_fts")
    op.add_column(
        "chunks",
        sa.Column(
            "text_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, text)", persisted=True),
            nullable=True,
        ),
    )
    op.create_index("ix_chunks_text_tsv", "chunks", ["text_tsv"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_chunks_text_tsv", table_name="chunks")
    op.drop_column("chunks", "text_tsv")
    op.execute("CREATE INDEX idx_chunks_fts ON chunks USING gin (to_tsvector('english', text))")
