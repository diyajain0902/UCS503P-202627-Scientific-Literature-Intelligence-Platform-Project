"""Paper summaries, cross-paper synthesis, structured extraction, comparison (FR-12 to FR-15).

Evidence is gathered by searching inside the selected paper(s) for each facet of interest, so the
bounded context still covers the whole paper. Every claim or extracted field must cite a supplied
passage; anything else is dropped (claims) or reported as ``unknown`` (fields).
"""

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError, InvalidInputError, MalformedModelOutputError, NotFoundError
from app.db.models import Analysis, AnalysisKind, AnalysisStatus, Paper
from app.generation.analysis_prompts import (
    ANALYSIS_PROMPT_VERSION,
    EXTRACTION_FIELDS,
    EXTRACTION_SYSTEM,
    FIELD_QUERIES,
    SUMMARY_SYSTEM,
    SYNTHESIS_SYSTEM,
    ExtractionModelOutput,
    extraction_json_schema,
)
from app.generation.citations import check_citations, has_substance
from app.generation.prompts import EvidencePassage, ModelAnswer, answer_json_schema, build_prompt
from app.generation.provider import GenerationProvider, GenerationRequest
from app.retrieval.search import ChunkHit
from app.services.search import SearchService

logger = logging.getLogger(__name__)

SUMMARY_QUERIES = (
    "main contribution of this paper",
    "proposed method and approach",
    "experiments and datasets",
    "main results",
    "limitations and future work",
)
MAX_SYNTHESIS_PAPERS = 5
UNKNOWN = "unknown"
DIFFERENT_DATASETS = (
    "Results were reported on different datasets or settings; they are shown side by side and "
    "are not directly comparable."
)


@dataclass(frozen=True)
class _Evidence:
    passage: EvidencePassage
    hit: ChunkHit

    def snapshot(self) -> dict[str, object]:
        return {
            "label": self.passage.label,
            "chunk_id": str(self.hit.chunk.id),
            "paper_id": str(self.hit.paper.id),
            "paper_title": self.hit.paper.title,
            "arxiv_id": self.hit.paper.arxiv_id,
            "arxiv_version": self.hit.paper.arxiv_version,
            "page_start": self.hit.chunk.page_start,
            "page_end": self.hit.chunk.page_end,
            "score": round(self.hit.score, 6),
            "text": self.hit.chunk.text,
        }


class AnalysisService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        search: SearchService,
        provider: GenerationProvider,
        per_query_k: int = 2,
        max_context_chars: int = 12000,
    ) -> None:
        self._sessions = session_factory
        self._search = search
        self._provider = provider
        self._per_query_k = per_query_k
        self._max_context_chars = max_context_chars

    # ---- evidence ----------------------------------------------------------------------------

    def _papers(self, paper_ids: list[uuid.UUID]) -> list[Paper]:
        with self._sessions() as session:
            found = {p.id: p for p in session.scalars(select(Paper).where(Paper.id.in_(paper_ids)))}
        missing = [str(pid) for pid in paper_ids if pid not in found]
        if missing:
            raise NotFoundError(f"paper(s) not found: {', '.join(missing)}")
        return [found[pid] for pid in paper_ids]

    def _gather(self, queries: list[tuple[str, uuid.UUID]], k: int) -> list[_Evidence]:
        """Search each (query, paper) pair; keep unique chunks in order within the budget."""
        evidence: list[_Evidence] = []
        seen: set[uuid.UUID] = set()
        used = 0
        for query, paper_id in queries:
            for hit in self._search.search(query, k, [paper_id]).hits:
                if hit.chunk.id in seen:
                    continue
                if used + len(hit.chunk.text) > self._max_context_chars and evidence:
                    return evidence
                seen.add(hit.chunk.id)
                used += len(hit.chunk.text)
                label = f"P{len(evidence) + 1}"
                evidence.append(
                    _Evidence(
                        EvidencePassage(
                            label,
                            hit.chunk.text,
                            hit.paper.title,
                            hit.chunk.page_start,
                            hit.chunk.page_end,
                        ),
                        hit,
                    )
                )
        return evidence

    # ---- generation --------------------------------------------------------------------------

    def _claims(
        self, system: str, instruction: str, evidence: list[_Evidence]
    ) -> tuple[str, dict[str, object], Any]:
        passages = [e.passage for e in evidence]
        generation = self._provider.generate(
            GenerationRequest(
                system, build_prompt(instruction, passages, heading="Task"), answer_json_schema()
            )
        )
        try:
            parsed = ModelAnswer.model_validate_json(generation.text)
        except ValidationError as exc:
            raise MalformedModelOutputError(
                "The model's output did not match the required format"
            ) from exc
        checked = check_citations(parsed, {p.label for p in passages})
        claims = [
            {
                "index": i,
                "text": claim.text,
                "support": claim.support,
                "citations": [{"label": c.label, "valid": c.valid} for c in claim.citations],
            }
            for i, claim in enumerate(c for c in checked.claims if c.support == "cited")
        ]
        status = (
            AnalysisStatus.COMPLETED.value if claims else AnalysisStatus.INSUFFICIENT_EVIDENCE.value
        )
        return status, {"claims": claims}, generation

    def _fields(self, evidence: list[_Evidence]) -> tuple[str, dict[str, object], Any]:
        passages = [e.passage for e in evidence]
        labels = {p.label for p in passages}
        generation = self._provider.generate(
            GenerationRequest(
                EXTRACTION_SYSTEM,
                build_prompt("Extract the fields for this paper.", passages, heading="Task"),
                extraction_json_schema(),
            )
        )
        try:
            parsed = ExtractionModelOutput.model_validate_json(generation.text)
        except ValidationError as exc:
            raise MalformedModelOutputError(
                "The model's output did not match the required format"
            ) from exc
        by_field: dict[str, dict[str, object]] = {}
        for item in parsed.fields:
            if item.field in by_field:
                continue
            citations: list[dict[str, Any]] = []
            for raw in item.citations:
                label = raw.strip().strip("[]").upper()
                if label and label not in {c["label"] for c in citations}:
                    citations.append({"label": label, "valid": label in labels})
            value = " ".join(item.value.split())
            cited = any(c["valid"] for c in citations)
            known = cited and value.lower() != UNKNOWN and has_substance(value)
            by_field[item.field] = {
                "field": item.field,
                "value": value if known else UNKNOWN,
                "status": "found" if known else UNKNOWN,
                "citations": citations if known else [],
            }
        fields = [
            by_field.get(
                name, {"field": name, "value": UNKNOWN, "status": UNKNOWN, "citations": []}
            )
            for name in EXTRACTION_FIELDS
        ]
        found = any(f["status"] == "found" for f in fields)
        status = (
            AnalysisStatus.COMPLETED.value if found else AnalysisStatus.INSUFFICIENT_EVIDENCE.value
        )
        return status, {"fields": fields}, generation

    def _run(
        self,
        kind: AnalysisKind,
        paper_ids: list[uuid.UUID],
        topic: str | None,
        evidence: list[_Evidence],
        produce: Any,
    ) -> Analysis:
        started = time.perf_counter()
        config = {
            "per_query_k": self._per_query_k,
            "max_context_chars": self._max_context_chars,
            "generation_options": dict(self._provider.options),
            "embedding_model": self._search.embedding_model,
        }
        analysis = Analysis(
            id=uuid.uuid4(),
            kind=kind.value,
            paper_ids=[str(p) for p in paper_ids],
            topic=topic,
            evidence=[e.snapshot() for e in evidence],
            prompt_version=ANALYSIS_PROMPT_VERSION,
            config=config,
        )
        try:
            if not evidence:
                analysis.status = AnalysisStatus.INSUFFICIENT_EVIDENCE.value
                analysis.reason = "No passages were found for this paper selection."
                analysis.result = {}
            else:
                status, result, generation = produce(evidence)
                analysis.status = status
                analysis.result = result
                analysis.generation_model = generation.model
                if status != AnalysisStatus.COMPLETED.value:
                    analysis.reason = "The passages did not support any cited statement."
        except AppError as exc:
            analysis.status = AnalysisStatus.ERROR.value
            analysis.reason = exc.message
            analysis.result = {}
            analysis.latency_ms = round((time.perf_counter() - started) * 1000, 1)
            self._save(analysis)
            raise
        analysis.latency_ms = round((time.perf_counter() - started) * 1000, 1)
        self._save(analysis)
        return analysis

    def _save(self, analysis: Analysis) -> None:
        with self._sessions() as session:
            session.add(analysis)
            session.commit()
        logger.info(
            "analysis_done",
            extra={
                "analysis_id": str(analysis.id),
                "kind": analysis.kind,
                "status": analysis.status,
            },
        )

    # ---- use cases ---------------------------------------------------------------------------

    def summarize(self, paper_id: uuid.UUID) -> Analysis:
        paper = self._papers([paper_id])[0]
        evidence = self._gather([(q, paper.id) for q in SUMMARY_QUERIES], self._per_query_k)
        return self._run(
            AnalysisKind.SUMMARY,
            [paper.id],
            None,
            evidence,
            lambda ev: self._claims(SUMMARY_SYSTEM, f"Summarise the paper '{paper.title}'.", ev),
        )

    def synthesize(self, topic: str, paper_ids: list[uuid.UUID]) -> Analysis:
        cleaned = " ".join(topic.split())
        if not cleaned:
            raise InvalidInputError("topic must contain text")
        unique = list(dict.fromkeys(paper_ids))
        if not 2 <= len(unique) <= MAX_SYNTHESIS_PAPERS:
            raise InvalidInputError(f"select between 2 and {MAX_SYNTHESIS_PAPERS} papers")
        papers = self._papers(unique)
        evidence = self._gather([(cleaned, p.id) for p in papers], self._per_query_k + 1)
        return self._run(
            AnalysisKind.SYNTHESIS,
            unique,
            cleaned,
            evidence,
            lambda ev: self._claims(
                SYNTHESIS_SYSTEM, f"What do these papers say about: {cleaned}", ev
            ),
        )

    def extract(self, paper_id: uuid.UUID) -> Analysis:
        paper = self._papers([paper_id])[0]
        queries = [(FIELD_QUERIES[f], paper.id) for f in EXTRACTION_FIELDS]
        evidence = self._gather(queries, self._per_query_k)
        return self._run(AnalysisKind.EXTRACTION, [paper.id], None, evidence, self._fields)

    def latest(self, kind: AnalysisKind, paper_id: uuid.UUID) -> Analysis | None:
        with self._sessions() as session:
            return session.scalars(
                select(Analysis)
                .where(
                    Analysis.kind == kind.value,
                    Analysis.status != AnalysisStatus.ERROR.value,
                    Analysis.paper_ids.contains([str(paper_id)]),
                )
                .order_by(Analysis.created_at.desc())
                .limit(1)
            ).first()

    def get(self, analysis_id: uuid.UUID) -> Analysis:
        with self._sessions() as session:
            analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            raise NotFoundError(f"analysis {analysis_id} not found")
        return analysis

    def compare(self, paper_ids: list[uuid.UUID], extract_missing: bool) -> dict[str, Any]:
        """Side-by-side extracted fields (FR-15). Never ranks; flags non-comparable results."""
        unique = list(dict.fromkeys(paper_ids))
        if not 2 <= len(unique) <= MAX_SYNTHESIS_PAPERS:
            raise InvalidInputError(f"select between 2 and {MAX_SYNTHESIS_PAPERS} papers")
        papers = self._papers(unique)
        columns: list[dict[str, Any]] = []
        datasets: set[str] = set()
        for paper in papers:
            extraction = self.latest(AnalysisKind.EXTRACTION, paper.id)
            if extraction is None and extract_missing:
                extraction = self.extract(paper.id)
            fields: dict[str, dict[str, Any]] = {}
            if extraction is not None:
                raw_fields = extraction.result.get("fields")
                if isinstance(raw_fields, list):
                    fields = {str(f["field"]): f for f in raw_fields if isinstance(f, dict)}
            datasets.add(str(fields.get("dataset", {}).get("value", UNKNOWN)).strip().lower())
            columns.append(
                {
                    "paper_id": str(paper.id),
                    "title": paper.title,
                    "analysis_id": str(extraction.id) if extraction else None,
                    "fields": fields,
                }
            )
        caveats = []
        known = datasets - {UNKNOWN}
        if len(known) > 1 or (known and UNKNOWN in datasets):
            caveats.append(DIFFERENT_DATASETS)
        if any(c["analysis_id"] is None for c in columns):
            caveats.append("Some papers have not been extracted yet.")
        return {"fields": list(EXTRACTION_FIELDS), "papers": columns, "caveats": caveats}
