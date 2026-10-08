"""SQLAlchemy ORM models. The schema itself is owned by Alembic migrations."""

import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
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
    PDF_UPLOAD = "pdf_upload"


class AnswerStatus(enum.StrEnum):
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


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
        Index("ix_chunks_text_tsv", "text_tsv", postgresql_using="gin"),
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
    # Stored full-text vector for BM25 search (FR-24, migration 0006); never loaded with the row.
    text_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english'::regconfig, text)", persisted=True), deferred=True
    )

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
    """arXiv identifier for imports; SHA-256 of the file for uploads."""
    display_name: Mapped[str | None] = mapped_column(String(300))
    """Human-readable label (upload title or file name); never used as a path."""
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


class Query(Base):
    """A question asked through grounded Q&A (FR-18)."""

    __tablename__ = "queries"
    __table_args__ = (CheckConstraint("top_k >= 1", name="ck_queries_top_k"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text)
    top_k: Mapped[int] = mapped_column(Integer)
    paper_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    answer: Mapped["Answer | None"] = relationship(
        back_populates="query", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class Answer(Base):
    """The outcome of a query, with the configuration that produced it (NFR-09)."""

    __tablename__ = "answers"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(AnswerStatus)})", name="ck_answers_status"),
        CheckConstraint(
            "status = 'answered' OR reason IS NOT NULL", name="ck_answers_reason_unless_answered"
        ),
        CheckConstraint("latency_ms >= 0", name="ck_answers_latency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("queries.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    claims: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    """[{"index": int, "text": str, "support": "cited" | "unsupported"}]"""
    generation_model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32))
    embedding_model: Mapped[str] = mapped_column(String(128))
    config: Mapped[dict[str, object]] = mapped_column(JSONB)
    """Retrieval and generation settings used for this answer (NFR-09)."""
    retrieval_ms: Mapped[float | None] = mapped_column(Float)
    generation_ms: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    query: Mapped[Query] = relationship(back_populates="answer")
    evidence: Mapped[list["AnswerEvidence"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="AnswerEvidence.rank"
    )
    citations: Mapped[list["AnswerCitation"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="[AnswerCitation.claim_index, AnswerCitation.position]",
    )


class AnswerEvidence(Base):
    """A passage shown to the model; snapshotted so history survives deletion of the paper."""

    __tablename__ = "answer_evidence"
    __table_args__ = (
        UniqueConstraint("answer_id", "label", name="uq_answer_evidence_answer_label"),
        CheckConstraint("rank >= 1", name="ck_answer_evidence_rank"),
        CheckConstraint(
            "page_start >= 1 AND page_start <= page_end", name="ck_answer_evidence_pages"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(8))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"), index=True
    )
    paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id", ondelete="SET NULL"))
    paper_title: Mapped[str] = mapped_column(Text)
    arxiv_id: Mapped[str | None] = mapped_column(String(32))
    arxiv_version: Mapped[int | None] = mapped_column(Integer)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class AnswerCitation(Base):
    """A label cited by a claim, with the server's validity verdict (FR-10)."""

    __tablename__ = "answer_citations"
    __table_args__ = (
        UniqueConstraint(
            "answer_id", "claim_index", "position", name="uq_answer_citations_position"
        ),
        CheckConstraint("claim_index >= 0 AND position >= 0", name="ck_answer_citations_index"),
        CheckConstraint(
            "valid = (evidence_id IS NOT NULL)", name="ck_answer_citations_valid_iff_linked"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    answer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("answers.id", ondelete="CASCADE"), index=True
    )
    claim_index: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(32))
    valid: Mapped[bool] = mapped_column(Boolean)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("answer_evidence.id", ondelete="CASCADE")
    )

    # Lets the unit of work insert evidence rows before the citations that reference them.
    evidence: Mapped[AnswerEvidence | None] = relationship()


class AnalysisKind(enum.StrEnum):
    SUMMARY = "summary"
    SYNTHESIS = "synthesis"
    EXTRACTION = "extraction"


class AnalysisStatus(enum.StrEnum):
    COMPLETED = "completed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    ERROR = "error"


class Analysis(Base):
    """A summary, cross-paper synthesis, or structured extraction (FR-12 to FR-14).

    ``evidence`` is a snapshot of the passages shown to the model, so results stay inspectable
    after the source paper is deleted. ``result`` holds validated claims or fields with their
    citation verdicts.
    """

    __tablename__ = "analyses"
    __table_args__ = (
        CheckConstraint(f"kind IN ({_values(AnalysisKind)})", name="ck_analyses_kind"),
        CheckConstraint(f"status IN ({_values(AnalysisStatus)})", name="ck_analyses_status"),
        CheckConstraint(
            "status = 'completed' OR reason IS NOT NULL", name="ck_analyses_reason_unless_completed"
        ),
        CheckConstraint("latency_ms >= 0", name="ck_analyses_latency"),
        Index("ix_analyses_kind_created", "kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    paper_ids: Mapped[list[str]] = mapped_column(JSONB)
    topic: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, object]] = mapped_column(JSONB)
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    generation_model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict[str, object]] = mapped_column(JSONB)
    latency_ms: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
