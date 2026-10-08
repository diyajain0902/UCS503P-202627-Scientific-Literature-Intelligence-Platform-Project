"""Summaries, synthesis, structured extraction, and comparison endpoints (FR-12 to FR-15)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.v1.routes import ERRORS, ContainerDep
from app.core.errors import NotFoundError
from app.db.models import Analysis, AnalysisKind

router = APIRouter(responses={**ERRORS, 504: ERRORS[503]}, tags=["analysis"])


class AnalysisOut(BaseModel):
    id: uuid.UUID
    kind: Literal["summary", "synthesis", "extraction"]
    paper_ids: list[uuid.UUID]
    topic: str | None
    status: Literal["completed", "insufficient_evidence", "error"]
    reason: str | None
    result: dict[str, Any]
    """``{"claims": [...]}`` for summaries and syntheses; ``{"fields": [...]}`` for extractions.
    Every claim or found field has at least one citation verified against ``evidence``.
    """
    evidence: list[dict[str, Any]]
    generation_model: str | None
    prompt_version: str
    latency_ms: float
    created_at: datetime

    @classmethod
    def of(cls, analysis: Analysis) -> "AnalysisOut":
        return cls.model_validate(
            {
                "id": analysis.id,
                "kind": analysis.kind,
                "paper_ids": analysis.paper_ids,
                "topic": analysis.topic,
                "status": analysis.status,
                "reason": analysis.reason,
                "result": analysis.result,
                "evidence": analysis.evidence,
                "generation_model": analysis.generation_model,
                "prompt_version": analysis.prompt_version,
                "latency_ms": analysis.latency_ms,
                "created_at": analysis.created_at,
            }
        )


class SynthesisRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    paper_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)


class CompareRequest(BaseModel):
    paper_ids: list[uuid.UUID] = Field(min_length=2, max_length=5)
    extract_missing: bool = True


class CompareOut(BaseModel):
    fields: list[str]
    papers: list[dict[str, Any]]
    caveats: list[str]


@router.post("/papers/{paper_id}/summary", response_model=AnalysisOut)
def summarize(paper_id: uuid.UUID, container: ContainerDep) -> AnalysisOut:
    return AnalysisOut.of(container.analysis.summarize(paper_id))


@router.post("/papers/{paper_id}/extraction", response_model=AnalysisOut)
def extract(paper_id: uuid.UUID, container: ContainerDep) -> AnalysisOut:
    return AnalysisOut.of(container.analysis.extract(paper_id))


@router.get("/papers/{paper_id}/latest/{kind}", response_model=AnalysisOut)
def latest(
    paper_id: uuid.UUID, kind: Literal["summary", "extraction"], container: ContainerDep
) -> AnalysisOut:
    found = container.analysis.latest(AnalysisKind(kind), paper_id)
    if found is None:
        raise NotFoundError(f"no {kind} for paper {paper_id} yet")
    return AnalysisOut.of(found)


@router.post("/synthesis", response_model=AnalysisOut)
def synthesize(body: SynthesisRequest, container: ContainerDep) -> AnalysisOut:
    return AnalysisOut.of(container.analysis.synthesize(body.topic, body.paper_ids))


@router.post("/compare", response_model=CompareOut)
def compare(body: CompareRequest, container: ContainerDep) -> CompareOut:
    return CompareOut.model_validate(
        container.analysis.compare(body.paper_ids, body.extract_missing)
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: uuid.UUID, container: ContainerDep) -> AnalysisOut:
    return AnalysisOut.of(container.analysis.get(analysis_id))
