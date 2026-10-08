"""Request/response schemas for the v1 API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import IngestionJob
from app.services.corpus import PaperSummary
from app.services.search import SearchResult


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class ArxivImportRequest(BaseModel):
    arxiv_id: str = Field(min_length=1, max_length=64, examples=["1706.03762"])


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    state: str
    source_ref: str
    display_name: str | None
    paper_id: uuid.UUID | None
    error: str | None
    attempts: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None

    @classmethod
    def of(cls, job: IngestionJob) -> "JobOut":
        return cls.model_validate(job)


class PaperOut(BaseModel):
    id: uuid.UUID
    source: str
    arxiv_id: str | None
    arxiv_version: int | None
    title: str
    authors: list[str]
    abstract: str | None
    categories: list[str]
    published_at: datetime | None
    page_count: int | None
    chunk_count: int
    created_at: datetime

    @classmethod
    def of(cls, summary: PaperSummary) -> "PaperOut":
        paper = summary.paper
        return cls(
            id=paper.id,
            source=paper.source,
            arxiv_id=paper.arxiv_id,
            arxiv_version=paper.arxiv_version,
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            categories=paper.categories,
            published_at=paper.published_at,
            page_count=summary.page_count,
            chunk_count=summary.chunk_count,
            created_at=paper.created_at,
        )


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)
    paper_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class SearchPaperRef(BaseModel):
    id: uuid.UUID
    title: str
    arxiv_id: str | None
    arxiv_version: int | None


class SearchHitOut(BaseModel):
    rank: int
    chunk_id: uuid.UUID
    score: float
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int
    paper: SearchPaperRef


class SearchResponse(BaseModel):
    query: str
    top_k: int
    embedding_model: str
    took_ms: float
    results: list[SearchHitOut]

    @classmethod
    def of(cls, query: str, top_k: int, result: SearchResult) -> "SearchResponse":
        return cls(
            query=query,
            top_k=top_k,
            embedding_model=result.embedding_model,
            took_ms=result.took_ms,
            results=[
                SearchHitOut(
                    rank=rank,
                    chunk_id=hit.chunk.id,
                    score=round(hit.score, 6),
                    text=hit.chunk.text,
                    page_start=hit.chunk.page_start,
                    page_end=hit.chunk.page_end,
                    char_start=hit.chunk.char_start,
                    char_end=hit.chunk.char_end,
                    paper=SearchPaperRef(
                        id=hit.paper.id,
                        title=hit.paper.title,
                        arxiv_id=hit.paper.arxiv_id,
                        arxiv_version=hit.paper.arxiv_version,
                    ),
                )
                for rank, hit in enumerate(result.hits, start=1)
            ],
        )


class CheckOut(BaseModel):
    ok: bool
    detail: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, CheckOut]
