"""Corpus management endpoints (FR-01, FR-03, FR-16, FR-17, FR-22, FR-23)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status
from pydantic import BaseModel

from app.api.v1.routes import ERRORS, ContainerDep
from app.api.v1.schemas import JobOut
from app.core.errors import DocumentRejectedError
from app.db.models import JobState

router = APIRouter(responses={**ERRORS, 409: ERRORS[404], 413: ERRORS[404]})

_READ_BLOCK = 1024 * 1024


class ArxivResultOut(BaseModel):
    arxiv_id: str
    version: int
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published_at: datetime | None
    stored_version: int | None
    """Version already in the corpus, or null if the paper has not been imported."""


class StatsOut(BaseModel):
    papers: int
    papers_by_source: dict[str, int]
    chunks: int
    pages: int
    jobs_by_state: dict[str, int]
    answers_by_status: dict[str, int]


class SettingsOut(BaseModel):
    """Read-only, non-secret configuration (FR-23). Never includes credentials or URLs with them."""

    embedding_model: str
    embedding_dimension: int
    chunk_window_tokens: int
    chunk_overlap_tokens: int
    generation_model: str
    generation_options: dict[str, object]
    qa_default_top_k: int
    qa_min_score: float
    search_max_top_k: int
    max_pdf_megabytes: int
    max_pdf_pages: int


@router.post(
    "/papers/upload",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingestion"],
    summary="Upload a PDF; it is validated now and ingested in the background",
)
async def upload_pdf(
    container: ContainerDep,
    response: Response,
    file: Annotated[UploadFile, File(description="A text-based PDF")],
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> JobOut:
    limit = container.settings.max_pdf_bytes
    data = bytearray()
    while block := await file.read(_READ_BLOCK):
        data.extend(block)
        if len(data) > limit:
            raise DocumentRejectedError(
                f"File is larger than the {limit // (1024 * 1024)} MB limit"
            )
    job, created = container.ingestion.request_upload(bytes(data), file.filename, title)
    if created:
        container.runner.submit(job.id)
    else:
        response.status_code = status.HTTP_200_OK
    return JobOut.of(job)


@router.delete("/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["corpus"])
def delete_paper(paper_id: uuid.UUID, container: ContainerDep) -> Response:
    container.corpus.delete_paper(paper_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs", response_model=list[JobOut], tags=["ingestion"])
def list_jobs(
    container: ContainerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    state: Annotated[JobState | None, Query()] = None,
) -> list[JobOut]:
    return [JobOut.of(j) for j in container.corpus.list_jobs(limit, state.value if state else None)]


@router.post("/jobs/{job_id}/retry", response_model=JobOut, status_code=202, tags=["ingestion"])
def retry_job(job_id: uuid.UUID, container: ContainerDep, response: Response) -> JobOut:
    job, created = container.ingestion.retry(job_id)
    if created:
        container.runner.submit(job.id)
    else:
        response.status_code = status.HTTP_200_OK
    return JobOut.of(job)


@router.get("/arxiv/search", response_model=list[ArxivResultOut], tags=["ingestion"])
def search_arxiv(
    container: ContainerDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    max_results: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[ArxivResultOut]:
    return [
        ArxivResultOut(
            arxiv_id=meta.arxiv_id,
            version=meta.version,
            title=meta.title,
            authors=meta.authors,
            abstract=meta.abstract,
            categories=meta.categories,
            published_at=meta.published_at,
            stored_version=stored,
        )
        for meta, stored in container.ingestion.search_arxiv(q, max_results)
    ]


@router.get("/categories", response_model=list[str], tags=["corpus"])
def categories(container: ContainerDep) -> list[str]:
    return container.corpus.categories()


@router.get("/stats", response_model=StatsOut, tags=["corpus"])
def stats(container: ContainerDep) -> StatsOut:
    s = container.corpus.stats()
    return StatsOut(
        papers=s.papers,
        papers_by_source=s.papers_by_source,
        chunks=s.chunks,
        pages=s.pages,
        jobs_by_state=s.jobs_by_state,
        answers_by_status=s.answers_by_status,
    )


@router.get("/settings", response_model=SettingsOut, tags=["health"])
def settings_view(container: ContainerDep) -> SettingsOut:
    s = container.settings
    qa = container.qa.describe()
    return SettingsOut(
        embedding_model=s.embedding_model,
        embedding_dimension=s.embedding_dimension,
        chunk_window_tokens=s.chunk_window_tokens,
        chunk_overlap_tokens=s.chunk_overlap_tokens,
        generation_model=str(qa["generation_model"]),
        generation_options=dict(qa["generation_options"]),
        qa_default_top_k=s.qa_default_top_k,
        qa_min_score=s.qa_min_score,
        search_max_top_k=s.search_max_top_k,
        max_pdf_megabytes=s.max_pdf_bytes // (1024 * 1024),
        max_pdf_pages=s.max_pdf_pages,
    )
