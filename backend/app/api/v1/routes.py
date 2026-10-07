"""Corpus, ingestion, and search endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status

from app.api.v1.schemas import (
    ArxivImportRequest,
    ErrorResponse,
    JobOut,
    Page,
    PaperOut,
    SearchRequest,
    SearchResponse,
)
from app.container import Container
from app.core.errors import InvalidInputError

ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (404, 422, 502, 503)
}

router = APIRouter(responses=ERRORS)


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


@router.post(
    "/papers/arxiv",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["ingestion"],
    summary="Queue import of an arXiv paper (returns the in-flight job if one exists)",
)
def import_arxiv_paper(
    body: ArxivImportRequest, container: ContainerDep, response: Response
) -> JobOut:
    job, created = container.ingestion.request_arxiv_import(body.arxiv_id)
    if created:
        container.runner.submit(job.id)
    else:
        response.status_code = status.HTTP_200_OK
    return JobOut.of(job)


@router.get("/jobs/{job_id}", response_model=JobOut, tags=["ingestion"])
def get_job(job_id: uuid.UUID, container: ContainerDep) -> JobOut:
    return JobOut.of(container.corpus.get_job(job_id))


@router.get("/papers", response_model=Page[PaperOut], tags=["corpus"])
def list_papers(
    container: ContainerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> Page[PaperOut]:
    summaries, total = container.corpus.list_papers(limit, offset)
    return Page[PaperOut](
        items=[PaperOut.of(s) for s in summaries], total=total, limit=limit, offset=offset
    )


@router.get("/papers/{paper_id}", response_model=PaperOut, tags=["corpus"])
def get_paper(paper_id: uuid.UUID, container: ContainerDep) -> PaperOut:
    return PaperOut.of(container.corpus.get_paper(paper_id))


@router.post("/search", response_model=SearchResponse, tags=["search"])
def search(body: SearchRequest, container: ContainerDep) -> SearchResponse:
    settings = container.settings
    if len(body.query) > settings.search_max_query_chars:
        raise InvalidInputError(
            f"query must be at most {settings.search_max_query_chars} characters"
        )
    top_k = body.top_k or settings.search_default_top_k
    result = container.search.search(body.query, top_k, body.paper_ids)
    return SearchResponse.of(body.query, top_k, result)
