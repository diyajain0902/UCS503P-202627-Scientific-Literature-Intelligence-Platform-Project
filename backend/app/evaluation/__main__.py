"""Evaluation command line. Uses SLIP_* settings; point SLIP_DATABASE_URL at the eval database.

Usage::

    python -m app.evaluation build-corpus
    python -m app.evaluation check-labels
    python -m app.evaluation retrieval [--min-recall-at-5 X]
    python -m app.evaluation qa
"""

import argparse
import json
import os
import sys
from pathlib import Path

from app.container import build_container
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.evaluation.corpus import (
    CorpusMismatchError,
    build_corpus,
    check_labels,
    job_failures,
    verify_corpus,
)
from app.evaluation.dataset import EVAL_DIR, load_dataset, load_manifest
from app.evaluation.runner import (
    base_record,
    measure_cold_starts,
    run_qa,
    run_retrieval,
    write_record,
)


def _fail(message: str) -> None:
    """Print a failure; in GitHub Actions also emit an annotation (visible without login)."""
    print(message)
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::error::{message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.evaluation")
    parser.add_argument("command", choices=["build-corpus", "check-labels", "retrieval", "qa"])
    parser.add_argument("--manifest", type=Path, default=EVAL_DIR / "corpus.json")
    parser.add_argument("--dataset", type=Path, default=EVAL_DIR / "qa_v1.json")
    parser.add_argument("--runs-dir", type=Path, default=EVAL_DIR / "runs")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--search-mode",
        choices=["dense", "bm25", "hybrid", "hybrid_rerank"],
        default=None,
        help="search strategy mode for retrieval evaluation",
    )
    parser.add_argument(
        "--min-recall-at-5",
        type=float,
        default=None,
        help="exit non-zero if Recall@5 is below this value (CI regression gate)",
    )
    parser.add_argument("--no-record", action="store_true", help="do not write a run record")
    parser.add_argument(
        "--judge",
        action="store_true",
        help="qa: also judge semantic support of each cited claim with the local model",
    )
    parser.add_argument(
        "--cold-samples",
        type=int,
        default=3,
        help="qa: questions asked right after unloading the model, to measure cold start",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging("WARNING")
    container = build_container(settings)
    manifest = load_manifest(args.manifest.resolve())
    try:
        if args.command == "build-corpus":
            for line in build_corpus(manifest, container.ingestion):
                print(line)
            failures = job_failures(container.session_factory)
            for failure in failures:
                _fail(f"FAILED {failure}")
            try:
                verify_corpus(manifest, container.session_factory)
            except CorpusMismatchError as exc:
                _fail(str(exc))
                return 1
            print(f"corpus ok: {len(manifest.papers)} papers")
            return 1 if failures else 0

        verify_corpus(manifest, container.session_factory)
        dataset = load_dataset(args.dataset.resolve())
        problems = check_labels(dataset, container.session_factory)
        for p in problems:
            _fail(f"LABEL {p.item_id} {p.arxiv_id}: {p.problem}: {p.quote!r}")
        if problems:
            return 2
        if args.command == "check-labels":
            print(
                f"labels ok: {len(dataset.answerable)} answerable, "
                f"{len(dataset.unanswerable)} unanswerable"
            )
            return 0

        record = base_record(args.command, dataset, args.dataset.resolve(), args.manifest.resolve())
        if args.command == "retrieval":
            record.update(
                run_retrieval(
                    dataset,
                    container.search,
                    container.session_factory,
                    args.top_k,
                    args.search_mode,
                )
            )
        else:
            if container.ollama is None:
                raise SystemExit("Q&A evaluation needs the Ollama provider")
            # Warm both models so the timed loop measures warm latency only (NFR-03).
            container.embedder.warm_up()
            container.ollama.warm_up()
            qa_config = dict(container.qa.describe())
            judge = container.ollama if args.judge else None
            record.update(run_qa(dataset, container.qa, qa_config, judge))
            if args.cold_samples:
                cold = measure_cold_starts(
                    dataset, container.qa, container.ollama.unload, args.cold_samples
                )
                record["metrics"]["cold_start_latency_ms"] = cold
        print(json.dumps(record["metrics"], indent=2))
        if not args.no_record:
            print(f"record: {write_record(record, args.runs_dir.resolve())}")
        if args.min_recall_at_5 is not None:
            recall = float(record["metrics"]["recall@5"])
            if recall < args.min_recall_at_5:
                _fail(f"GATE FAILED: recall@5 {recall:.4f} < {args.min_recall_at_5:.4f}")
                return 3
            print(f"gate passed: recall@5 {recall:.4f} >= {args.min_recall_at_5:.4f}")
        return 0
    finally:
        container.close()


if __name__ == "__main__":
    sys.exit(main())
