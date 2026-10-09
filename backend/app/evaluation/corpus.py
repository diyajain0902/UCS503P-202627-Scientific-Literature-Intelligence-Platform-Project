"""Build the evaluation corpus from the pinned manifest and check labels against it (AC-19.1)."""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Chunk, Document, IngestionJob, JobState, Paper
from app.evaluation.dataset import CorpusManifest, EvalDataset, normalize
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)


class CorpusMismatchError(RuntimeError):
    """The database does not contain exactly the pinned papers and versions."""


# arXiv rate-limits bursts (HTTP 429, timeouts), notably from shared CI runners. Failed papers are
# retried after these waits; papers that already succeeded are not fetched again.
RETRY_WAITS_SECONDS = (30.0, 90.0, 180.0)


def build_corpus(
    manifest: CorpusManifest,
    ingestion: IngestionService,
    sessions: sessionmaker[Session],
    sleep: Callable[[float], None] = time.sleep,
    retry_waits: Sequence[float] = RETRY_WAITS_SECONDS,
) -> tuple[list[str], list[str]]:
    """Ingest every pinned paper synchronously, retrying failures with backoff.

    Returns status lines and the failures of the final attempt (empty when every paper is ready).
    """
    lines: list[str] = []
    pending = [f"{paper.arxiv_id}v{paper.version}" for paper in manifest.papers]
    failures: list[str] = []
    for attempt in range(len(retry_waits) + 1):
        if attempt:
            wait = retry_waits[attempt - 1]
            lines.append(f"retrying {len(pending)} paper(s) after {wait:.0f} s")
            sleep(wait)
        failures = []
        for ref in pending:
            job, _ = ingestion.request_arxiv_import(ref)
            ingestion.run_job(job.id)
            with sessions() as session:
                done = session.get(IngestionJob, job.id)
            if done is not None and done.state == JobState.FAILED.value:
                failures.append(f"{ref}: {done.error}")
            else:
                lines.append(f"{ref}: {done.state if done else 'unknown'} ({job.id})")
        pending = [failure.split(":", 1)[0] for failure in failures]
        if not pending:
            break
    return lines, failures


def verify_corpus(manifest: CorpusManifest, sessions: sessionmaker[Session]) -> None:
    """Raise unless the database holds exactly the manifest's papers at the pinned versions."""
    expected = {(p.arxiv_id, p.version) for p in manifest.papers}
    with sessions() as session:
        rows = session.execute(
            select(Paper.arxiv_id, Paper.arxiv_version).join(
                Document, Document.paper_id == Paper.id
            )
        ).all()
    actual = {(str(a), int(v)) for a, v in rows if a is not None and v is not None}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise CorpusMismatchError(f"corpus mismatch: missing={missing} unexpected={extra}")


@dataclass(frozen=True)
class LabelProblem:
    item_id: str
    arxiv_id: str
    quote: str
    problem: str


def check_labels(dataset: EvalDataset, sessions: sessionmaker[Session]) -> list[LabelProblem]:
    """Every evidence quote must occur in at least one chunk of its paper."""
    with sessions() as session:
        rows = session.execute(
            select(Paper.arxiv_id, Chunk.text)
            .join(Document, Document.paper_id == Paper.id)
            .join(Chunk, Chunk.document_id == Document.id)
        ).all()
    by_paper: dict[str, list[str]] = {}
    for arxiv_id, text in rows:
        by_paper.setdefault(str(arxiv_id), []).append(normalize(text))
    problems: list[LabelProblem] = []
    for item in dataset.answerable:
        for evidence in item.evidence:
            chunks = by_paper.get(evidence.arxiv_id)
            if chunks is None:
                problems.append(
                    LabelProblem(item.id, evidence.arxiv_id, evidence.quote, "paper not in corpus")
                )
            elif not any(normalize(evidence.quote) in chunk for chunk in chunks):
                problems.append(
                    LabelProblem(
                        item.id, evidence.arxiv_id, evidence.quote, "quote not in any chunk"
                    )
                )
    return problems
