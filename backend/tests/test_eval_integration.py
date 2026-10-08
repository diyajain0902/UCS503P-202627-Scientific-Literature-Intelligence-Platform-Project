"""Evaluation tooling against real PostgreSQL with a synthetic corpus (AC-19.1, AC-19.3).

The corpus, questions, and labels here are synthetic test fixtures, not the evaluation set.
"""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.container import Container
from app.core.config import Settings
from app.evaluation.corpus import CorpusMismatchError, check_labels, verify_corpus
from app.evaluation.dataset import CorpusManifest, EvalDataset
from app.evaluation.runner import base_record, run_qa, run_retrieval, write_record
from app.ingestion.chunking import ChunkingConfig
from tests.fakes import (
    FakeArxiv,
    FakeProvider,
    answer_json,
    make_pdf,
    make_test_container,
    synthetic_metadata,
)

pytestmark = pytest.mark.integration

PAPER_A = ["Alpha transformers use eight attention heads per layer in this synthetic note. " * 3]
PAPER_B = ["Beta networks are trained for ninety epochs on synthetic graph data here. " * 3]

MANIFEST = CorpusManifest.model_validate(
    {
        "name": "synthetic",
        "version": "1",
        "domain": "test",
        "papers": [
            {"arxiv_id": "2101.00001", "version": 1, "title": "A"},
            {"arxiv_id": "2101.00002", "version": 1, "title": "B"},
        ],
    }
)


def _dataset(quote: str = "eight attention heads per layer") -> EvalDataset:
    common = {"labeler": "test", "labeled_on": date(2026, 10, 8), "review_status": "unreviewed"}
    return EvalDataset.model_validate(
        {
            "name": "synthetic-qa",
            "version": "1",
            "corpus": "synthetic",
            "items": [
                {
                    "id": "q001",
                    "kind": "answerable",
                    "question": "How many attention heads do alpha transformers use?",
                    "answer": "Eight",
                    "evidence": [{"arxiv_id": "2101.00001", "quote": quote}],
                    **common,
                },
                {
                    "id": "q002",
                    "kind": "unanswerable",
                    "question": "What is the boiling point of mercury?",
                    **common,
                },
            ],
        }
    )


@pytest.fixture
def container(
    sessions: sessionmaker[Session], database_url: str, tmp_path: Path
) -> Iterator[Container]:
    settings = Settings(
        database_url=database_url, ollama_base_url="http://127.0.0.1:1", qa_min_score=0.0
    )
    arxiv = FakeArxiv()
    arxiv.add(synthetic_metadata("2101.00001"), make_pdf(PAPER_A))
    arxiv.add(synthetic_metadata("2101.00002"), make_pdf(PAPER_B))
    built = make_test_container(
        settings, sessions, tmp_path, arxiv=arxiv, chunking=ChunkingConfig(32, 4)
    )
    for paper in MANIFEST.papers:
        job, _ = built.ingestion.request_arxiv_import(f"{paper.arxiv_id}v{paper.version}")
        built.ingestion.run_job(job.id)
    yield built
    built.close()


def test_verify_corpus_accepts_exact_manifest_and_rejects_others(container: Container) -> None:
    verify_corpus(MANIFEST, container.session_factory)
    other = MANIFEST.model_copy(
        update={
            "papers": [*MANIFEST.papers[:1], MANIFEST.papers[1].model_copy(update={"version": 2})]
        }
    )
    with pytest.raises(CorpusMismatchError, match=r"2101.00002"):
        verify_corpus(other, container.session_factory)


def test_check_labels_flags_quotes_missing_from_corpus(container: Container) -> None:
    assert check_labels(_dataset(), container.session_factory) == []
    problems = check_labels(_dataset("a quote that is nowhere"), container.session_factory)
    assert [(p.item_id, p.problem) for p in problems] == [("q001", "quote not in any chunk")]


def test_retrieval_run_scores_answerable_items_only(container: Container) -> None:
    result = run_retrieval(_dataset(), container.search, container.session_factory, top_k=5)
    assert result["metrics"]["recall@1"] == 1.0
    assert result["metrics"]["mrr"] == 1.0
    assert result["config"]["chunker_versions"] == ["tokwin-v1|test-whitespace|w32|o4"]
    items = {i["id"]: i for i in result["items"]}
    assert items["q001"]["first_relevant_rank"] == 1
    assert items["q002"]["first_relevant_rank"] is None and items["q002"]["top_score"] is not None


def test_qa_run_and_record(container: Container, tmp_path: Path) -> None:
    provider = container.qa._provider
    assert isinstance(provider, FakeProvider)
    provider.responses = [
        answer_json(("Alpha transformers use eight heads.", ["P1"])),
        answer_json(status="insufficient_evidence"),
    ]
    dataset = _dataset()
    result = run_qa(dataset, container.qa, container.qa.describe())
    metrics = result["metrics"]
    assert metrics["answer_rate_answerable"] == 1.0
    assert metrics["cited_relevant_rate_answerable"] == 1.0
    assert metrics["abstention_recall"] == 1.0
    assert metrics["false_answer_rate_unanswerable"] == 0.0
    assert metrics["citation_validity_rate"] == 1.0

    dataset_path = tmp_path / "ds.json"
    dataset_path.write_text(dataset.model_dump_json(), encoding="utf-8")
    manifest_path = tmp_path / "corpus.json"
    manifest_path.write_text(MANIFEST.model_dump_json(), encoding="utf-8")
    record = base_record("qa", dataset, dataset_path, manifest_path)
    record.update(result)
    assert record["dataset"]["items"] == 2
    assert record["dataset"]["labelers"] == ["test"]
    assert record["dataset"]["human_reviewed_items"] == 0
    assert len(record["dataset"]["sha256"]) == 64
    path = write_record(record, tmp_path / "runs")
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["metrics"] == metrics
    assert stored["config"]["prompt_version"] == "qa-v1"
