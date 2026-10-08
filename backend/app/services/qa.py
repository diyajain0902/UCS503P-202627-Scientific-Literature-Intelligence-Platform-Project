"""Grounded question answering (FR-09, FR-10, FR-11, FR-18).

Flow: validate -> retrieve -> drop passages below the relevance threshold (abstain early if none
remain) -> bounded, delimited context -> local model with a JSON schema -> schema validation ->
citation check -> persist. Every outcome except invalid input is persisted, including errors, so
history reflects what users saw.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.core.errors import AppError, InvalidInputError, MalformedModelOutputError, NotFoundError
from app.db.models import Answer, AnswerCitation, AnswerEvidence, AnswerStatus, Query
from app.generation.citations import CheckedAnswer, check_citations
from app.generation.prompts import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    EvidencePassage,
    ModelAnswer,
    answer_json_schema,
    build_prompt,
)
from app.generation.provider import GenerationProvider, GenerationRequest, GenerationResult
from app.retrieval.search import ChunkHit
from app.services.search import SearchResult, SearchService

logger = logging.getLogger(__name__)

NO_RELEVANT_PASSAGES = "No passage in the corpus was relevant enough to answer this question."
MODEL_ABSTAINED = (
    "The retrieved passages do not contain enough information to answer this question."
)
NO_VALID_CITATIONS = (
    "The model's answer cited no passage it was given, so it was withheld as unsupported."
)


@dataclass(frozen=True)
class QALimits:
    default_top_k: int
    max_top_k: int
    max_question_chars: int
    min_score: float
    max_context_chars: int


@dataclass(frozen=True)
class _Evidence:
    passage: EvidencePassage
    hit: ChunkHit
    rank: int


@dataclass
class _Outcome:
    status: AnswerStatus
    reason: str | None
    checked: CheckedAnswer | None = None
    generation: GenerationResult | None = None


def _select_evidence(hits: list[ChunkHit], min_score: float, max_chars: int) -> list[_Evidence]:
    """Keep passages above the threshold, in rank order, within the context character budget."""
    selected: list[_Evidence] = []
    used = 0
    for rank, hit in enumerate(hits, start=1):
        if hit.score < min_score:
            continue
        if used + len(hit.chunk.text) > max_chars and selected:
            break
        used += len(hit.chunk.text)
        label = f"P{len(selected) + 1}"
        selected.append(
            _Evidence(
                passage=EvidencePassage(
                    label=label,
                    text=hit.chunk.text,
                    paper_title=hit.paper.title,
                    page_start=hit.chunk.page_start,
                    page_end=hit.chunk.page_end,
                ),
                hit=hit,
                rank=rank,
            )
        )
    return selected


class QAService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        search: SearchService,
        provider: GenerationProvider,
        limits: QALimits,
    ) -> None:
        self._sessions = session_factory
        self._search = search
        self._provider = provider
        self._limits = limits

    def describe(self) -> dict[str, Any]:
        """Configuration that determines answers (recorded in evaluation runs)."""
        return {
            "default_top_k": self._limits.default_top_k,
            "min_score": self._limits.min_score,
            "max_context_chars": self._limits.max_context_chars,
            "generation_model": self._provider.model_name,
            "generation_options": dict(self._provider.options),
            "prompt_version": PROMPT_VERSION,
            "embedding_model": self._search.embedding_model,
            "retrieval": self._search.describe(),
        }

    # ---- asking
    # ---------------------------------------------------------------------------------------

    def ask(
        self, question: str, top_k: int | None = None, paper_ids: list[uuid.UUID] | None = None
    ) -> Answer:
        cleaned = " ".join(question.split())
        if not cleaned:
            raise InvalidInputError("question must contain text")
        if len(cleaned) > self._limits.max_question_chars:
            raise InvalidInputError(
                f"question must be at most {self._limits.max_question_chars} characters"
            )
        k = top_k or self._limits.default_top_k
        if not 1 <= k <= self._limits.max_top_k:
            raise InvalidInputError(f"top_k must be between 1 and {self._limits.max_top_k}")

        started = time.perf_counter()
        retrieval = self._search.search(cleaned, k, paper_ids)
        evidence = _select_evidence(
            retrieval.hits, self._limits.min_score, self._limits.max_context_chars
        )
        config = self._config(k, paper_ids, retrieval.embedding_model)

        if not evidence:
            outcome = _Outcome(AnswerStatus.INSUFFICIENT_EVIDENCE, NO_RELEVANT_PASSAGES)
            return self._persist(cleaned, k, paper_ids, outcome, [], config, retrieval, started)

        try:
            outcome = self._generate(cleaned, evidence)
        except AppError as exc:
            failed = _Outcome(AnswerStatus.ERROR, exc.message)
            self._persist(cleaned, k, paper_ids, failed, evidence, config, retrieval, started)
            raise
        return self._persist(cleaned, k, paper_ids, outcome, evidence, config, retrieval, started)

    def _generate(self, question: str, evidence: list[_Evidence]) -> _Outcome:
        passages = [e.passage for e in evidence]
        generation = self._provider.generate(
            GenerationRequest(
                system=SYSTEM_PROMPT,
                prompt=build_prompt(question, passages),
                json_schema=answer_json_schema(),
            )
        )
        try:
            parsed = ModelAnswer.model_validate_json(generation.text)
        except ValidationError as exc:
            detail = " (output was cut off at the token limit)" if generation.truncated else ""
            raise MalformedModelOutputError(
                f"The model's output did not match the required answer format{detail}"
            ) from exc

        checked = check_citations(parsed, {p.label for p in passages})
        if checked.invalid_citation_count or checked.dropped_claims:
            logger.warning(
                "model_answer_defects",
                extra={
                    "invalid_citations": checked.invalid_citation_count,
                    "dropped_claims": checked.dropped_claims,
                },
            )
        if checked.model_status == "insufficient_evidence":
            return _Outcome(AnswerStatus.INSUFFICIENT_EVIDENCE, MODEL_ABSTAINED, None, generation)
        if not checked.has_supported_claim:
            return _Outcome(
                AnswerStatus.INSUFFICIENT_EVIDENCE, NO_VALID_CITATIONS, None, generation
            )
        return _Outcome(AnswerStatus.ANSWERED, None, checked, generation)

    def _config(
        self, top_k: int, paper_ids: list[uuid.UUID] | None, embedding_model: str
    ) -> dict[str, Any]:
        return {
            "top_k": top_k,
            "paper_ids": [str(p) for p in paper_ids or []],
            "min_score": self._limits.min_score,
            "max_context_chars": self._limits.max_context_chars,
            "embedding_model": embedding_model,
            "generation_model": self._provider.model_name,
            "generation_options": dict(self._provider.options),
            "prompt_version": PROMPT_VERSION,
            "retrieval": self._search.describe(),
        }

    # ---- persistence
    # ----------------------------------------------------------------------------------

    def _persist(
        self,
        question: str,
        top_k: int,
        paper_ids: list[uuid.UUID] | None,
        outcome: _Outcome,
        evidence: list[_Evidence],
        config: dict[str, Any],
        retrieval: SearchResult,
        started: float,
    ) -> Answer:
        generation = outcome.generation
        checked = outcome.checked
        query = Query(question=question, top_k=top_k, paper_ids=[str(p) for p in paper_ids or []])
        answer = Answer(
            id=uuid.uuid4(),
            query=query,
            status=outcome.status.value,
            reason=outcome.reason,
            claims=[
                {"index": i, "text": claim.text, "support": claim.support}
                for i, claim in enumerate(checked.claims if checked else [])
            ],
            generation_model=generation.model if generation else None,
            prompt_version=PROMPT_VERSION,
            embedding_model=str(config["embedding_model"]),
            config=config,
            retrieval_ms=retrieval.took_ms,
            generation_ms=generation.duration_ms if generation else None,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            prompt_tokens=generation.prompt_tokens if generation else None,
            completion_tokens=generation.completion_tokens if generation else None,
        )
        by_label: dict[str, AnswerEvidence] = {}
        evidence_rows: list[AnswerEvidence] = []
        citation_rows: list[AnswerCitation] = []
        for item in evidence:
            hit = item.hit
            row = AnswerEvidence(
                id=uuid.uuid4(),
                label=item.passage.label,
                rank=item.rank,
                score=round(hit.score, 6),
                chunk_id=hit.chunk.id,
                paper_id=hit.paper.id,
                paper_title=hit.paper.title,
                arxiv_id=hit.paper.arxiv_id,
                arxiv_version=hit.paper.arxiv_version,
                page_start=hit.chunk.page_start,
                page_end=hit.chunk.page_end,
                text=hit.chunk.text,
            )
            by_label[row.label] = row
            evidence_rows.append(row)
        for claim_index, claim in enumerate(checked.claims if checked else []):
            for position, citation in enumerate(claim.citations):
                target = by_label.get(citation.label) if citation.valid else None
                citation_rows.append(
                    AnswerCitation(
                        claim_index=claim_index,
                        position=position,
                        label=citation.label[:32],
                        valid=target is not None,
                        evidence=target,
                    )
                )
        # Assigning (rather than lazily appending) leaves both collections loaded after the
        # session closes, so callers can serialize the answer without a database round trip.
        answer.evidence = evidence_rows
        answer.citations = citation_rows
        with self._sessions() as session:
            session.add(answer)
            session.commit()
        logger.info(
            "qa_answer",
            extra={
                "answer_id": str(answer.id),
                "status": answer.status,
                "evidence": len(evidence),
                "claims": len(answer.claims),
                "latency_ms": answer.latency_ms,
            },
        )
        return answer

    # ---- reading
    # --------------------------------------------------------------------------------------

    def get(self, answer_id: uuid.UUID) -> Answer:
        with self._sessions() as session:
            answer = session.scalars(
                select(Answer)
                .where(Answer.id == answer_id)
                .options(
                    selectinload(Answer.query),
                    selectinload(Answer.evidence),
                    selectinload(Answer.citations),
                )
            ).one_or_none()
        if answer is None:
            raise NotFoundError(f"answer {answer_id} not found")
        return answer

    def history(self, limit: int, offset: int) -> tuple[list[Answer], int]:
        with self._sessions() as session:
            total = session.scalar(select(func.count()).select_from(Answer)) or 0
            answers = session.scalars(
                select(Answer)
                .options(selectinload(Answer.query))
                .order_by(Answer.created_at.desc(), Answer.id)
                .limit(limit)
                .offset(offset)
            ).all()
        return list(answers), int(total)
