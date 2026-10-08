"""Initial schema: papers, documents, chunks (pgvector), ingestion jobs.

Revision ID: 0001
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "papers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("arxiv_id", sa.String(32), nullable=True),
        sa.Column("arxiv_version", sa.Integer(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("categories", postgresql.JSONB(), nullable=False),
        sa.Column("published_at", _TS, nullable=True),
        sa.Column("source_updated_at", _TS, nullable=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("arxiv_id", name="uq_papers_arxiv_id"),
        sa.CheckConstraint("source IN ('arxiv', 'upload')", name="ck_papers_source"),
        sa.CheckConstraint(
            "(source = 'arxiv') = (arxiv_id IS NOT NULL)", name="ck_papers_arxiv_id_matches_source"
        ),
        sa.CheckConstraint(
            "arxiv_version IS NULL OR arxiv_version >= 1", name="ck_papers_arxiv_version"
        ),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="CASCADE", name="fk_documents_paper_id"),
            nullable=False,
        ),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("extractor_version", sa.String(64), nullable=False),
        sa.Column("chunker_version", sa.String(128), nullable=False),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("paper_id", name="uq_documents_paper_id"),
        sa.UniqueConstraint("sha256", name="uq_documents_sha256"),
        sa.CheckConstraint("byte_size > 0", name="ck_documents_byte_size"),
        sa.CheckConstraint("page_count > 0", name="ck_documents_page_count"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_documents_sha256"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE", name="fk_chunks_document_id"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_chunks_ordinal"),
        sa.CheckConstraint("page_start >= 1 AND page_start <= page_end", name="ck_chunks_pages"),
        sa.CheckConstraint("char_start >= 0 AND char_start < char_end", name="ck_chunks_chars"),
        sa.CheckConstraint("token_count > 0", name="ck_chunks_token_count"),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=False),
        sa.Column(
            "paper_id",
            sa.Uuid(),
            sa.ForeignKey("papers.id", ondelete="CASCADE", name="fk_ingestion_jobs_paper_id"),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", _TS, nullable=True),
        sa.CheckConstraint(
            "state IN ('queued', 'fetching', 'extracting', 'chunking', 'embedding',"
            " 'ready', 'failed')",
            name="ck_ingestion_jobs_state",
        ),
        sa.CheckConstraint("kind IN ('arxiv_import')", name="ck_ingestion_jobs_kind"),
        sa.CheckConstraint("attempts >= 0", name="ck_ingestion_jobs_attempts"),
        sa.CheckConstraint(
            "(state = 'failed') = (error IS NOT NULL)", name="ck_ingestion_jobs_error_iff_failed"
        ),
    )
    op.create_index("ix_ingestion_jobs_state", "ingestion_jobs", ["state"])
    op.create_index("ix_ingestion_jobs_paper_id", "ingestion_jobs", ["paper_id"])
    op.create_index(
        "uq_ingestion_jobs_active_source",
        "ingestion_jobs",
        ["source_ref"],
        unique=True,
        postgresql_where=sa.text("state NOT IN ('ready', 'failed')"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("papers")
    # The vector extension is left installed: other databases objects may depend on it.
