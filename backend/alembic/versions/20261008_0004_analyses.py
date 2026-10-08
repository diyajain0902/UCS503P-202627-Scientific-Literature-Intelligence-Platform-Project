"""Analyses: paper summaries, cross-paper syntheses, structured extractions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("paper_ids", postgresql.JSONB(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("generation_model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "kind IN ('summary', 'synthesis', 'extraction')", name="ck_analyses_kind"
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'insufficient_evidence', 'error')", name="ck_analyses_status"
        ),
        sa.CheckConstraint(
            "status = 'completed' OR reason IS NOT NULL", name="ck_analyses_reason_unless_completed"
        ),
        sa.CheckConstraint("latency_ms >= 0", name="ck_analyses_latency"),
    )
    op.create_index("ix_analyses_kind_created", "analyses", ["kind", "created_at"])


def downgrade() -> None:
    op.drop_table("analyses")
