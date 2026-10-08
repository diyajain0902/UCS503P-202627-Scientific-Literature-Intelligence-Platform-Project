"""arXiv ingestion pipeline (FR-02, FR-04 to FR-07, FR-17).

Each job moves through explicit states; progress is committed per state so clients can poll it. All
derived data for a paper (document + chunks) is replaced in a single transaction, so a failed run
never leaves partial chunks behind.
"""

import hashlib
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError, DocumentRejectedError
from app.db.models import (
    TERMINAL_JOB_STATES,
    Chunk,
    Document,
    IngestionJob,
    JobKind,
    JobState,
    Paper,
    PaperSource,
)
from app.ingestion.arxiv import ArxivId, ArxivMetadata, ArxivSource
from app.ingestion.chunking import ChunkingConfig, Tokenizer, chunk_document
from app.ingestion.pdf import EXTRACTOR_VERSION, extract_pdf
from app.ingestion.storage import FileStore
from app.retrieval.embedding import Embedder

logger = logging.getLogger(__name__)

_MAX_ERROR_CHARS = 1000


def _now() -> datetime:
    return datetime.now(UTC)


def _apply_metadata(paper: Paper, meta: ArxivMetadata) -> None:
    paper.arxiv_version = meta.version
    paper.title = meta.title
    paper.authors = meta.authors
    paper.abstract = meta.abstract
    paper.categories = meta.categories
    paper.published_at = meta.published_at
    paper.source_updated_at = meta.updated_at


class IngestionService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        arxiv: ArxivSource,
        embedder: Embedder,
        tokenizer_provider: Callable[[], Tokenizer],
        store: FileStore,
        chunking: ChunkingConfig,
        max_pdf_bytes: int,
        max_pdf_pages: int,
    ) -> None:
        self._sessions = session_factory
        self._arxiv = arxiv
        self._embedder = embedder
        self._tokenizer_provider = tokenizer_provider
        self._store = store
        self._chunking = chunking
        self._max_pdf_bytes = max_pdf_bytes
        self._max_pdf_pages = max_pdf_pages

    # ---- requests
    # -------------------------------------------------------------------------------------------

    def request_arxiv_import(self, raw_id: str) -> tuple[IngestionJob, bool]:
        """Create a queued job, or return the in-flight job for the same identifier. Returns
        (job, created).
        """
        source_ref = str(ArxivId.parse(raw_id))
        with self._sessions() as session:
            existing = self._active_job(session, source_ref)
            if existing is not None:
                return existing, False
            job = IngestionJob(
                kind=JobKind.ARXIV_IMPORT.value,
                state=JobState.QUEUED.value,
                source_ref=source_ref,
                attempts=0,
            )
            session.add(job)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = self._active_job(session, source_ref)
                if existing is None:
                    raise
                return existing, False
            return job, True

    @staticmethod
    def _active_job(session: Session, source_ref: str) -> IngestionJob | None:
        terminal = [state.value for state in TERMINAL_JOB_STATES]
        return session.scalars(
            select(IngestionJob).where(
                IngestionJob.source_ref == source_ref, IngestionJob.state.not_in(terminal)
            )
        ).first()

    # ---- execution
    # ------------------------------------------------------------------------------------------

    def run_job(self, job_id: uuid.UUID) -> None:
        """Execute a job to completion. Never raises; failures are recorded on the job."""
        try:
            self._run(job_id)
        except AppError as exc:
            logger.info("ingestion_job_failed", extra={"job_id": str(job_id), "reason": exc.code})
            self._fail(job_id, exc.message)
        except Exception:
            logger.exception("ingestion_job_crashed", extra={"job_id": str(job_id)})
            self._fail(job_id, "Unexpected internal error during ingestion; see server logs.")

    def _transition(
        self, job_id: uuid.UUID, state: JobState, *, start: bool = False
    ) -> IngestionJob:
        with self._sessions() as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                raise RuntimeError(f"job {job_id} disappeared")
            job.state = state.value
            if start:
                job.attempts += 1
            session.commit()
            return job

    def _fail(self, job_id: uuid.UUID, message: str) -> None:
        with self._sessions() as session:
            job = session.get(IngestionJob, job_id)
            if job is None:
                return
            job.state = JobState.FAILED.value
            job.error = message[:_MAX_ERROR_CHARS]
            job.finished_at = _now()
            session.commit()

    def _run(self, job_id: uuid.UUID) -> None:
        job = self._transition(job_id, JobState.FETCHING, start=True)
        meta = self._arxiv.fetch_metadata(ArxivId.parse(job.source_ref))
        tokenizer = self._tokenizer_provider()
        chunker_version = self._chunking.version(tokenizer.name)

        if self._finish_if_unchanged(job_id, meta, chunker_version):
            return

        pdf = self._arxiv.download_pdf(meta.arxiv_id, meta.version, self._max_pdf_bytes)
        sha256 = hashlib.sha256(pdf).hexdigest()

        self._transition(job_id, JobState.EXTRACTING)
        extracted = extract_pdf(pdf, self._max_pdf_pages)

        self._transition(job_id, JobState.CHUNKING)
        specs = chunk_document(extracted, sha256, tokenizer, self._chunking)
        if not specs:
            raise DocumentRejectedError("No text chunks could be produced from this PDF")

        self._transition(job_id, JobState.EMBEDDING)
        vectors = self._embedder.embed([spec.text for spec in specs])

        key = self._store.save(sha256, pdf)
        old_key: str | None = None
        try:
            with self._sessions() as session:
                paper = session.scalars(
                    select(Paper).where(Paper.arxiv_id == meta.arxiv_id)
                ).one_or_none()
                if paper is None:
                    paper = Paper(source=PaperSource.ARXIV.value, arxiv_id=meta.arxiv_id)
                    session.add(paper)
                _apply_metadata(paper, meta)
                if paper.document is not None:
                    old_key = paper.document.storage_key
                    session.delete(paper.document)
                    session.flush()
                duplicate = session.scalars(
                    select(Document).where(Document.sha256 == sha256)
                ).first()
                if duplicate is not None:
                    raise DocumentRejectedError("This PDF is already stored for another paper")
                document = Document(
                    paper=paper,
                    sha256=sha256,
                    storage_key=key,
                    byte_size=len(pdf),
                    page_count=extracted.page_count,
                    extractor_version=EXTRACTOR_VERSION,
                    chunker_version=chunker_version,
                    embedding_model=self._embedder.model_name,
                )
                session.add(document)
                session.flush()
                session.add_all(
                    Chunk(
                        id=spec.id,
                        document_id=document.id,
                        ordinal=spec.ordinal,
                        page_start=spec.page_start,
                        page_end=spec.page_end,
                        char_start=spec.char_start,
                        char_end=spec.char_end,
                        token_count=spec.token_count,
                        text=spec.text,
                        embedding=vector,
                    )
                    for spec, vector in zip(specs, vectors, strict=True)
                )
                self._mark_ready(session, job_id, paper.id)
                session.commit()
        except BaseException:
            if not self._key_referenced(key):
                self._store.delete(key)
            raise
        if old_key is not None and old_key != key:
            self._store.delete(old_key)
        logger.info(
            "ingestion_job_ready",
            extra={
                "job_id": str(job_id),
                "arxiv_id": f"{meta.arxiv_id}v{meta.version}",
                "pages": extracted.page_count,
                "chunks": len(specs),
            },
        )

    def _finish_if_unchanged(
        self, job_id: uuid.UUID, meta: ArxivMetadata, chunker_version: str
    ) -> bool:
        """Idempotency (AC-02.1): same version, chunker, and embedder ⇒ refresh metadata only."""
        with self._sessions() as session:
            paper = session.scalars(
                select(Paper).where(Paper.arxiv_id == meta.arxiv_id)
            ).one_or_none()
            if paper is None or paper.document is None:
                return False
            document = paper.document
            if (
                paper.arxiv_version != meta.version
                or document.chunker_version != chunker_version
                or document.embedding_model != self._embedder.model_name
                or document.extractor_version != EXTRACTOR_VERSION
            ):
                return False
            _apply_metadata(paper, meta)
            self._mark_ready(session, job_id, paper.id)
            session.commit()
            return True

    @staticmethod
    def _mark_ready(session: Session, job_id: uuid.UUID, paper_id: uuid.UUID) -> None:
        job = session.get(IngestionJob, job_id)
        if job is None:
            raise RuntimeError(f"job {job_id} disappeared")
        job.paper_id = paper_id
        job.state = JobState.READY.value
        job.error = None
        job.finished_at = _now()

    def _key_referenced(self, key: str) -> bool:
        with self._sessions() as session:
            return (
                session.scalars(select(Document.id).where(Document.storage_key == key)).first()
                is not None
            )
