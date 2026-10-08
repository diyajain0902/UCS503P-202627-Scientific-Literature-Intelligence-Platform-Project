"""SQLAlchemy ORM models. The schema itself is owned by Alembic migrations."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Fixed by the schema (ADR-0003, FR-06). Changing it requires a migration.
EMBEDDING_DIMENSION = 384


class Base(DeclarativeBase):
    # Must match the names used in Alembic migrations (verified by `alembic check` in integration
    # tests).
    metadata = MetaData(
        naming_convention={
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s",
            "ix": "ix_%(table_name)s_%(column_0_name)s",
        }
    )


class PaperSource(enum.StrEnum):
    ARXIV = "arxiv"
    UPLOAD = "upload"


class JobState(enum.StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    READY = "ready"
    FAILED = "failed"


TERMINAL_JOB_STATES = frozenset({JobState.READY, JobState.FAILED})


class JobKind(enum.StrEnum):
    ARXIV_IMPORT = "arxiv_import"


def _values(enum_cls: type[enum.StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum_cls)


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(f"source IN ({_values(PaperSource)})", name="ck_papers_source"),
        CheckConstraint(
            "(source = 'arxiv') = (arxiv_id IS NOT NULL)", name="ck_papers_arxiv_id_matches_source"
        ),
        CheckConstraint(
            "arxiv_version IS NULL OR arxiv_version >= 1", name="ck_papers_arxiv_version"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(16))
    arxiv_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    arxiv_version: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(JSONB, default=list)
    abstract: Mapped[str | None] = mapped_column(Text)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document | None"] = relationship(
        back_populates="paper", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class Document(Base):
    """The PDF currently backing a paper. One per paper; replaced on re-ingestion of a new
    version.
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_documents_byte_size"),
        CheckConstraint("page_count > 0", name="ck_documents_page_count"),
        CheckConstraint("length(sha256) = 64", name="ck_documents_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    paper_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), unique=True
    )
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    storage_key: Mapped[str] = mapped_column(String(128))
    byte_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int] = mapped_column(Integer)
    extractor_version: Mapped[str] = mapped_column(String(64))
    chunker_version: Mapped[str] = mapped_column(String(128))
    embedding_model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    paper: Mapped[Paper] = relationship(back_populates="document")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chunk.ordinal",
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_chunks_ordinal"),
        CheckConstraint("page_start >= 1 AND page_start <= page_end", name="ck_chunks_pages"),
        CheckConstraint("char_start >= 0 AND char_start < char_end", name="ck_chunks_chars"),
        CheckConstraint("token_count > 0", name="ck_chunks_token_count"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION))

    document: Mapped[Document] = relationship(back_populates="chunks")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(f"state IN ({_values(JobState)})", name="ck_ingestion_jobs_state"),
        CheckConstraint(f"kind IN ({_values(JobKind)})", name="ck_ingestion_jobs_kind"),
        CheckConstraint("attempts >= 0", name="ck_ingestion_jobs_attempts"),
        CheckConstraint(
            "(state = 'failed') = (error IS NOT NULL)", name="ck_ingestion_jobs_error_iff_failed"
        ),
        # At most one in-flight job per source reference (prevents duplicate concurrent imports).
        Index(
            "uq_ingestion_jobs_active_source",
            "source_ref",
            unique=True,
            postgresql_where=text("state NOT IN ('ready', 'failed')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default=JobState.QUEUED.value, index=True)
    source_ref: Mapped[str] = mapped_column(String(64))
    paper_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("papers.id", ondelete="CASCADE"), index=True
    )
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
