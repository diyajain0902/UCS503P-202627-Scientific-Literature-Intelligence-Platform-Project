"""Read-side corpus queries (FR-07; full corpus management is FR-16, M4)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError
from app.db.models import Chunk, Document, IngestionJob, Paper


@dataclass(frozen=True)
class PaperSummary:
    paper: Paper
    page_count: int | None
    chunk_count: int


class CorpusService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def _summaries(
        self, session: Session, paper_filter: ColumnElement[bool] | None, limit: int, offset: int
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
        if paper_filter is not None:
            statement = statement.where(paper_filter)
        return [
            PaperSummary(paper=paper, page_count=pages, chunk_count=int(count))
            for paper, pages, count in session.execute(statement).all()
        ]

    def list_papers(self, limit: int, offset: int) -> tuple[list[PaperSummary], int]:
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(Paper)) or 0
            return self._summaries(session, None, limit, offset), int(total)

    def get_paper(self, paper_id: uuid.UUID) -> PaperSummary:
        with self._sessions() as session:
            found = self._summaries(session, Paper.id == paper_id, 1, 0)
        if not found:
            raise NotFoundError(f"paper {paper_id} not found")
        return found[0]

    def get_job(self, job_id: uuid.UUID) -> IngestionJob:
        with self._sessions() as session:
            job = session.get(IngestionJob, job_id)
        if job is None:
            raise NotFoundError(f"job {job_id} not found")
        return job
