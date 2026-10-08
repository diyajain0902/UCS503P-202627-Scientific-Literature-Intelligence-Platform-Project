"""Corpus browsing and management (FR-07, FR-16, FR-17, FR-22)."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, and_, extract, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError
from app.db.models import Answer, Chunk, Document, IngestionJob, Paper
from app.ingestion.storage import FileStore


@dataclass(frozen=True)
class PaperSummary:
    paper: Paper
    page_count: int | None
    chunk_count: int


@dataclass(frozen=True)
class PaperFilter:
    """All fields optional; combined with AND (FR-16)."""

    source: str | None = None
    category: str | None = None
    year: int | None = None
    title: str | None = None

    def conditions(self) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if self.source:
            conditions.append(Paper.source == self.source)
        if self.category:
            conditions.append(Paper.categories.contains([self.category]))
        if self.year:
            conditions.append(extract("year", Paper.published_at) == self.year)
        if self.title:
            escaped = self.title.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            conditions.append(Paper.title.ilike(f"%{escaped}%", escape="\\"))
        return conditions


@dataclass(frozen=True)
class CorpusStats:
    papers: int
    papers_by_source: dict[str, int]
    chunks: int
    pages: int
    jobs_by_state: dict[str, int]
    answers_by_status: dict[str, int] = field(default_factory=dict)


class CorpusService:
    def __init__(self, session_factory: sessionmaker[Session], store: FileStore) -> None:
        self._sessions = session_factory
        self._store = store

    def _summaries(
        self, session: Session, conditions: list[ColumnElement[bool]], limit: int, offset: int
    ) -> list[PaperSummary]:
        chunk_counts = (
            select(Chunk.document_id, func.count().label("n"))
            .group_by(Chunk.document_id)
            .subquery()
        )
        statement = (
            select(Paper, Document.page_count, func.coalesce(chunk_counts.c.n, 0))
            .outerjoin(Document, Document.paper_id == Paper.id)
            .outerjoin(chunk_counts, chunk_counts.c.document_id == Document.id)
            .order_by(Paper.created_at.desc(), Paper.id)
            .limit(limit)
            .offset(offset)
        )
        if conditions:
            statement = statement.where(and_(*conditions))
        return [
            PaperSummary(paper=paper, page_count=pages, chunk_count=int(count))
            for paper, pages, count in session.execute(statement).all()
        ]

    def list_papers(
        self, limit: int, offset: int, filters: PaperFilter | None = None
    ) -> tuple[list[PaperSummary], int]:
        conditions = (filters or PaperFilter()).conditions()
        with self._sessions() as session:
            count = select(func.count()).select_from(Paper)
            if conditions:
                count = count.where(and_(*conditions))
            total = session.scalar(count) or 0
            return self._summaries(session, conditions, limit, offset), int(total)

    def get_paper(self, paper_id: uuid.UUID) -> PaperSummary:
        with self._sessions() as session:
            found = self._summaries(session, [Paper.id == paper_id], 1, 0)
        if not found:
            raise NotFoundError(f"paper {paper_id} not found")
        return found[0]

    def delete_paper(self, paper_id: uuid.UUID) -> None:
        """Delete a paper with its document, chunks, and stored file (AC-07.3, AC-16.2).

        Q&A history keeps its evidence snapshots (foreign keys become NULL).
        """
        with self._sessions() as session:
            paper = session.get(Paper, paper_id)
            if paper is None:
                raise NotFoundError(f"paper {paper_id} not found")
            key = paper.document.storage_key if paper.document is not None else None
            session.delete(paper)
            session.commit()
        if key is not None:
            self._store.delete(key)

    def get_job(self, job_id: uuid.UUID) -> IngestionJob:
        with self._sessions() as session:
            job = session.get(IngestionJob, job_id)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        return job

    def list_jobs(self, limit: int, state: str | None = None) -> list[IngestionJob]:
        with self._sessions() as session:
            statement = select(IngestionJob).order_by(
                IngestionJob.created_at.desc(), IngestionJob.id
            )
            if state:
                statement = statement.where(IngestionJob.state == state)
            return list(session.scalars(statement.limit(limit)).all())

    def categories(self) -> list[str]:
        with self._sessions() as session:
            rows = session.execute(
                select(func.jsonb_array_elements_text(Paper.categories).label("c")).distinct()
            ).all()
        return sorted(str(r.c) for r in rows)

    def stats(self) -> CorpusStats:
        with self._sessions() as session:

            def grouped(column: ColumnElement[str]) -> dict[str, int]:
                rows = session.execute(select(column, func.count()).group_by(column)).all()
                return {str(key): int(n) for key, n in rows}

            return CorpusStats(
                papers=int(session.scalar(select(func.count()).select_from(Paper)) or 0),
                papers_by_source=grouped(Paper.source),  # type: ignore[arg-type]
                chunks=int(session.scalar(select(func.count()).select_from(Chunk)) or 0),
                pages=int(session.scalar(select(func.sum(Document.page_count))) or 0),
                jobs_by_state=grouped(IngestionJob.state),  # type: ignore[arg-type]
                answers_by_status=grouped(Answer.status),  # type: ignore[arg-type]
            )
