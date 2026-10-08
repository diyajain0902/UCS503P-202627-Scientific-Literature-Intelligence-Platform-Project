"""Evaluation runs and their records (FR-19, FR-20, AC-19.3).

Every run writes a JSON record under ``eval/runs/`` with the dataset and manifest hashes, git
commit, hardware, configuration, aggregate metrics, and per-item results, so any number in a report
can be traced to a run.
"""

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import AppError
from app.db.models import Document
from app.evaluation.dataset import REPO_ROOT, EvalDataset, EvalItem, is_relevant
from app.evaluation.metrics import mean_reciprocal_rank, percentile, ratio, recall_at_k
from app.services.qa import QAService
from app.services.search import SearchService

RETRIEVAL_KS = (1, 5, 10)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git() -> dict[str, Any]:
    git = shutil.which("git")

    def run(*args: str) -> str:
        if git is None:
            return ""
        # Fixed arguments only; no user input reaches the command line.
        return subprocess.run(  # noqa: S603
            [git, *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
        ).stdout.strip()

    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}


def _power_source() -> str:
    """ "ac", "battery", or "unknown". Latency depends heavily on it on laptops (measured in M3)."""
    if sys.platform != "win32":
        return "unknown"
    import ctypes

    class _PowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    status = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return "unknown"
    return {0: "battery", 1: "ac"}.get(status.ACLineStatus, "unknown")


def _hardware() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "power_source": _power_source(),
    }


def _chunker_versions(sessions: sessionmaker[Session]) -> list[str]:
    with sessions() as session:
        return sorted(set(session.scalars(select(Document.chunker_version)).all()))


def base_record(
    kind: str, dataset: EvalDataset, dataset_path: Path, manifest_path: Path
) -> dict[str, Any]:
    labelers = sorted({item.labeler for item in dataset.items})
    reviewed = sum(1 for item in dataset.items if item.review_status == "human_reviewed")
    return {
        "kind": kind,
        "started_at": datetime.now(UTC).isoformat(),
        "dataset": {
            "name": dataset.name,
            "version": dataset.version,
            "path": _display_path(dataset_path),
            "sha256": _sha256(dataset_path),
            "items": len(dataset.items),
            "answerable": len(dataset.answerable),
            "unanswerable": len(dataset.unanswerable),
            "labelers": labelers,
            "human_reviewed_items": reviewed,
        },
        "corpus_manifest": {
            "path": _display_path(manifest_path),
            "sha256": _sha256(manifest_path),
        },
        "git": _git(),
        "hardware": _hardware(),
    }


def run_retrieval(
    dataset: EvalDataset, search: SearchService, sessions: sessionmaker[Session], top_k: int
) -> dict[str, Any]:
    rankings: list[list[bool]] = []
    latencies: list[float] = []
    items: list[dict[str, Any]] = []
    for item in dataset.items:
        result = search.search(item.question, top_k)
        latencies.append(result.took_ms)
        flags = [is_relevant(item, h.paper.arxiv_id, h.chunk.text) for h in result.hits]
        top_score = result.hits[0].score if result.hits else None
        first = next((i + 1 for i, f in enumerate(flags) if f), None)
        if item.kind == "answerable":
            rankings.append(flags)
        items.append(
            {
                "id": item.id,
                "kind": item.kind,
                "first_relevant_rank": first,
                "top_score": round(top_score, 6) if top_score is not None else None,
                "relevant_scores": [
                    round(h.score, 6) for h, f in zip(result.hits, flags, strict=True) if f
                ],
                "top": [
                    {
                        "arxiv_id": h.paper.arxiv_id,
                        "pages": [h.chunk.page_start, h.chunk.page_end],
                        "score": round(h.score, 6),
                        "relevant": f,
                    }
                    for h, f in zip(result.hits[:5], flags[:5], strict=True)
                ],
                "search_ms": result.took_ms,
            }
        )
    metrics = {f"recall@{k}": recall_at_k(rankings, k) for k in RETRIEVAL_KS}
    metrics["mrr"] = mean_reciprocal_rank(rankings)
    metrics["search_ms_p50"] = percentile(latencies, 50)
    metrics["search_ms_p95"] = percentile(latencies, 95)
    return {
        "config": {
            "top_k": top_k,
            "embedding_model": search.embedding_model,
            "chunker_versions": _chunker_versions(sessions),
        },
        "metrics": metrics,
        "items": items,
    }


def _cited_relevant(item: EvalItem, answer: Any) -> bool:
    by_label = {e.label: e for e in answer.evidence}
    for citation in answer.citations:
        evidence = by_label.get(citation.label)
        if citation.valid and evidence and is_relevant(item, evidence.arxiv_id, evidence.text):
            return True
    return False


def run_qa(dataset: EvalDataset, qa: QAService, qa_config: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    latencies: list[float] = []
    for item in dataset.items:
        started = time.perf_counter()
        try:
            answer = qa.ask(item.question)
        except AppError as exc:
            items.append(
                {"id": item.id, "kind": item.kind, "status": "error", "error": exc.message}
            )
            continue
        latencies.append(answer.latency_ms)
        citations = list(answer.citations)
        items.append(
            {
                "id": item.id,
                "kind": item.kind,
                "status": answer.status,
                "reason": answer.reason,
                "claims": [c["text"] for c in answer.claims],
                "citations_total": len(citations),
                "citations_valid": sum(1 for c in citations if c.valid),
                "cited_relevant": _cited_relevant(item, answer)
                if item.kind == "answerable"
                else None,
                "evidence_count": len(answer.evidence),
                "latency_ms": answer.latency_ms,
                "wall_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        )

    answerable = [i for i in items if i["kind"] == "answerable"]
    unanswerable = [i for i in items if i["kind"] == "unanswerable"]
    abstained = [i for i in items if i["status"] == "insufficient_evidence"]
    answered = [i for i in answerable if i["status"] == "answered"]
    cit_total = sum(i.get("citations_total", 0) for i in items)
    cit_valid = sum(i.get("citations_valid", 0) for i in items)
    metrics: dict[str, Any] = {
        "answer_rate_answerable": ratio(len(answered), len(answerable)),
        "cited_relevant_rate_answerable": ratio(
            sum(1 for i in answerable if i.get("cited_relevant")), len(answerable)
        ),
        "cited_relevant_rate_of_answered": ratio(
            sum(1 for i in answered if i.get("cited_relevant")), len(answered)
        ),
        "abstention_recall": ratio(
            sum(1 for i in unanswerable if i["status"] == "insufficient_evidence"),
            len(unanswerable),
        ),
        "abstention_precision": ratio(
            sum(1 for i in abstained if i["kind"] == "unanswerable"), len(abstained)
        ),
        "false_answer_rate_unanswerable": ratio(
            sum(1 for i in unanswerable if i["status"] == "answered"), len(unanswerable)
        ),
        "citation_validity_rate": ratio(cit_valid, cit_total),
        "errors": sum(1 for i in items if i["status"] == "error"),
    }
    if latencies:
        # Callers must warm both models first; see app/evaluation/__main__.py.
        metrics["latency_ms_p50_warm"] = percentile(latencies, 50)
        metrics["latency_ms_p95_warm"] = percentile(latencies, 95)
        metrics["latency_ms_max"] = max(latencies)
    return {"config": qa_config, "metrics": metrics, "items": items}


def measure_cold_starts(
    dataset: EvalDataset, qa: QAService, unload: Callable[[], None], samples: int
) -> list[float]:
    """Latency of single questions asked right after the generation model was evicted."""
    latencies: list[float] = []
    for item in dataset.answerable[:samples]:
        unload()
        try:
            latencies.append(qa.ask(item.question).latency_ms)
        except AppError:
            continue
    return latencies


def write_record(record: dict[str, Any], runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    commit = str(record["git"]["commit"])[:7] or "nogit"
    path = runs_dir / f"{stamp}_{record['kind']}_{commit}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
