"""Grounded Q&A history: queries, answers, answer evidence, answer citations.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "queries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), nullable=False),
        sa.Column("paper_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("top_k >= 1", name="ck_queries_top_k"),
    )
    op.create_index("ix_queries_created_at", "queries", ["created_at"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "query_id",
            sa.Uuid(),
            sa.ForeignKey("queries.id", ondelete="CASCADE", name="fk_answers_query_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("claims", postgresql.JSONB(), nullable=False),
        sa.Column("generation_model", sa.String(128), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("retrieval_ms", sa.Float(), nullable=True),
        sa.Column("generation_ms", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("query_id", name="uq_answers_query_id"),
        sa.CheckConstraint(
            "status IN ('answered', 'insufficient_evidence', 'error')", name="ck_answers_status"
        ),
        sa.CheckConstraint(
            "status = 'answered' OR reason IS NOT NULL", name="ck_answers_reason_unless_answered"
        ),
        sa.CheckConstraint("latency_ms >= 0", name="ck_answers_latency"),
    )

    op.create_table(
        "answer_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "answer_id",
            sa.Uuid(),
            sa.ForeignKey("answers.id", ondelete="CASCADE", name="fk_answer_evidence_answer_id"),
            nullable=False,
        ),
        sa.Column("label", sa.String(8), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("chunks.id", ondelete="SET NULL", name="fk_answer_evidence_chunk_id"),
            nullable=True,
        ),
        sa.Column(
            "paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="SET NULL", name="fk_answer_evidence_paper_id"),
            nullable=True,
        ),
        sa.Column("paper_title", sa.Text(), nullable=False),
        sa.Column("arxiv_id", sa.String(32), nullable=True),
        sa.Column("arxiv_version", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("answer_id", "label", name="uq_answer_evidence_answer_label"),
        sa.CheckConstraint("rank >= 1", name="ck_answer_evidence_rank"),
        sa.CheckConstraint(
            "page_start >= 1 AND page_start <= page_end", name="ck_answer_evidence_pages"
        ),
    )
    op.create_index("ix_answer_evidence_answer_id", "answer_evidence", ["answer_id"])
    op.create_index("ix_answer_evidence_chunk_id", "answer_evidence", ["chunk_id"])

    op.create_table(
        "answer_citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "answer_id",
            sa.Uuid(),
            sa.ForeignKey("answers.id", ondelete="CASCADE", name="fk_answer_citations_answer_id"),
            nullable=False,
        ),
        sa.Column("claim_index", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(32), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column(
            "evidence_id",
            sa.Uuid(),
            sa.ForeignKey(
                "answer_evidence.id", ondelete="CASCADE", name="fk_answer_citations_evidence_id"
            ),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "answer_id", "claim_index", "position", name="uq_answer_citations_position"
        ),
        sa.CheckConstraint("claim_index >= 0 AND position >= 0", name="ck_answer_citations_index"),
        sa.CheckConstraint(
            "valid = (evidence_id IS NOT NULL)", name="ck_answer_citations_valid_iff_linked"
        ),
    )
    op.create_index("ix_answer_citations_answer_id", "answer_citations", ["answer_id"])


def downgrade() -> None:
    op.drop_table("answer_citations")
    op.drop_table("answer_evidence")
    op.drop_table("answers")
    op.drop_table("queries")
