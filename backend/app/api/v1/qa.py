"""Grounded Q&A endpoints (FR-09, FR-10, FR-11, FR-18)."""

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.api.v1.routes import ERRORS, ContainerDep
from app.core.errors import InvalidInputError
from app.db.models import Answer

router = APIRouter(responses={**ERRORS, 504: ERRORS[503]}, tags=["qa"])


class QARequest(BaseModel):
    question: str = Field(
        min_length=1, examples=["How many attention heads does the base model use?"]
    )
    top_k: int | None = Field(default=None, ge=1)
    paper_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class CitationOut(BaseModel):
    label: str
    valid: bool
    """True only if the label refers to a passage the model was actually given."""


class ClaimOut(BaseModel):
    index: int
    text: str
    support: Literal["cited", "unsupported"]
    """``cited``: has at least one valid citation (semantic support is not verified here)."""
    citations: list[CitationOut]


class EvidenceOut(BaseModel):
    label: str
    rank: int
    score: float
    chunk_id: uuid.UUID | None
    """Null if the source paper was deleted after answering; the snapshot below remains."""
    paper_id: uuid.UUID | None
    paper_title: str
    arxiv_id: str | None
    arxiv_version: int | None
    page_start: int
    page_end: int
    text: str


class TimingsOut(BaseModel):
    retrieval_ms: float | None
    generation_ms: float | None
    latency_ms: float


class AnswerOut(BaseModel):
    id: uuid.UUID
    query_id: uuid.UUID
    question: str
    status: Literal["answered", "insufficient_evidence", "error"]
    reason: str | None
    claims: list[ClaimOut]
    evidence: list[EvidenceOut]
    generation_model: str | None
    prompt_version: str
    embedding_model: str
    timings: TimingsOut
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: datetime

    @classmethod
    def of(cls, answer: Answer) -> "AnswerOut":
        by_claim: dict[int, list[CitationOut]] = defaultdict(list)
        for citation in answer.citations:
            by_claim[citation.claim_index].append(
                CitationOut(label=citation.label, valid=citation.valid)
            )
        return cls(
            id=answer.id,
            query_id=answer.query_id or answer.query.id,
            question=answer.query.question,
            status=answer.status,
            reason=answer.reason,
            claims=[
                ClaimOut(
                    index=int(str(claim["index"])),
                    text=str(claim["text"]),
                    support=claim["support"],
                    citations=by_claim[int(str(claim["index"]))],
                )
                for claim in answer.claims
            ],
            evidence=[
                EvidenceOut(
                    label=e.label,
                    rank=e.rank,
                    score=e.score,
                    chunk_id=e.chunk_id,
                    paper_id=e.paper_id,
                    paper_title=e.paper_title,
                    arxiv_id=e.arxiv_id,
                    arxiv_version=e.arxiv_version,
                    page_start=e.page_start,
                    page_end=e.page_end,
                    text=e.text,
                )
                for e in answer.evidence
            ],
            generation_model=answer.generation_model,
            prompt_version=answer.prompt_version,
            embedding_model=answer.embedding_model,
            timings=TimingsOut(
                retrieval_ms=answer.retrieval_ms,
                generation_ms=answer.generation_ms,
                latency_ms=answer.latency_ms,
            ),
            prompt_tokens=answer.prompt_tokens,
            completion_tokens=answer.completion_tokens,
            created_at=answer.created_at,
        )


class HistoryItemOut(BaseModel):
    id: uuid.UUID
    question: str
    status: str
    claim_count: int
    latency_ms: float
    created_at: datetime


class HistoryPage(BaseModel):
    items: list[HistoryItemOut]
    total: int
    limit: int
    offset: int


@router.post("/qa", response_model=AnswerOut, summary="Answer a question from the corpus")
def ask(body: QARequest, container: ContainerDep) -> AnswerOut:
    limit = container.settings.qa_max_question_chars
    if len(body.question) > limit:
        raise InvalidInputError(f"question must be at most {limit} characters")
    answer = container.qa.ask(body.question, body.top_k, body.paper_ids)
    return AnswerOut.of(answer)


@router.get("/qa", response_model=HistoryPage, summary="Recent questions and their outcomes")
def history(
    container: ContainerDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> HistoryPage:
    answers, total = container.qa.history(limit, offset)
    return HistoryPage(
        items=[
            HistoryItemOut(
                id=a.id,
                question=a.query.question,
                status=a.status,
                claim_count=len(a.claims),
                latency_ms=a.latency_ms,
                created_at=a.created_at,
            )
            for a in answers
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/qa/{answer_id}", response_model=AnswerOut)
def get_answer(answer_id: uuid.UUID, container: ContainerDep) -> AnswerOut:
    return AnswerOut.of(container.qa.get(answer_id))
