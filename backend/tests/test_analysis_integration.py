"""Summaries, synthesis, extraction, and comparison via the API on real PostgreSQL (M5).

The language model is a scripted fake; real-model checks are in test_analysis_ollama.py.
Covers AC-12.1/AC-13.1, AC-14.1, AC-14.2, AC-15.1.
"""

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import DependencyUnavailableError
from app.db.models import Analysis
from app.ingestion.chunking import ChunkingConfig
from app.main import create_app
from tests.fakes import (
    FakeArxiv,
    FakeProvider,
    answer_json,
    make_pdf,
    make_test_container,
    synthetic_metadata,
)

pytestmark = pytest.mark.integration

PAPER_A = [
    "We study sparse attention for long documents. Our method uses block sparse attention. " * 2,
    "We evaluate on the LongDocs benchmark and report 41.2 F1. A limitation is memory use. " * 2,
]
PAPER_B = [
    "We study graph neural networks for molecules. Our method uses message passing layers. " * 2,
    "We evaluate on the MolSet dataset and report 0.81 AUC. We do not test larger graphs. " * 2,
]


@dataclass
class Env:
    client: TestClient
    provider: FakeProvider
    sessions: sessionmaker[Session]
    a: str
    b: str


@pytest.fixture
def env(sessions: sessionmaker[Session], database_url: str, tmp_path: Path) -> Iterator[Env]:
    settings = Settings(database_url=database_url, ollama_base_url="http://127.0.0.1:1")
    arxiv = FakeArxiv()
    arxiv.add(synthetic_metadata("2101.00001", title="Sparse Attention Paper"), make_pdf(PAPER_A))
    arxiv.add(synthetic_metadata("2101.00002", title="Graph Molecule Paper"), make_pdf(PAPER_B))
    provider = FakeProvider()
    container = make_test_container(
        settings, sessions, tmp_path, arxiv=arxiv, provider=provider, chunking=ChunkingConfig(24, 4)
    )
    ids = []
    for arxiv_id in ("2101.00001", "2101.00002"):
        job, _ = container.ingestion.request_arxiv_import(arxiv_id)
        container.ingestion.run_job(job.id)
        ids.append(str(container.corpus.get_job(job.id).paper_id))
    with TestClient(create_app(container=container)) as client:
        yield Env(client, provider, sessions, ids[0], ids[1])
    container.close()


def fields_json(*fields: tuple[str, list[str], str]) -> str:
    return json.dumps({"fields": [{"field": f, "citations": c, "value": v} for f, c, v in fields]})


def test_summary_keeps_only_validly_cited_claims(env: Env) -> None:
    env.provider.responses = [
        answer_json(
            ("The paper studies sparse attention.", ["P1"]),
            ("It was cited 900 times.", ["P9"]),  # invented label
            ("P2", ["P2"]),  # label-only text
        )
    ]
    body = env.client.post(f"/api/v1/papers/{env.a}/summary").json()
    assert body["kind"] == "summary" and body["status"] == "completed"
    assert [c["text"] for c in body["result"]["claims"]] == ["The paper studies sparse attention."]
    assert body["result"]["claims"][0]["citations"] == [{"label": "P1", "valid": True}]
    assert body["evidence"] and {e["paper_id"] for e in body["evidence"]} == {env.a}
    assert body["prompt_version"] == "analysis-v1"

    prompt = env.provider.requests[0].prompt
    assert prompt.count("<passage ") == len(body["evidence"])
    assert "Task: Summarise the paper 'Sparse Attention Paper'." in prompt
    latest = env.client.get(f"/api/v1/papers/{env.a}/latest/summary").json()
    assert latest["id"] == body["id"]


def test_summary_without_cited_claims_is_insufficient(env: Env) -> None:
    env.provider.responses = [answer_json(("Unsupported.", ["P42"]))]
    body = env.client.post(f"/api/v1/papers/{env.a}/summary").json()
    assert body["status"] == "insufficient_evidence" and body["reason"]
    assert body["result"]["claims"] == []


def test_extraction_fields_are_cited_or_unknown(env: Env) -> None:
    env.provider.responses = [
        fields_json(
            ("task", ["P1"], "Sparse attention for long documents"),
            ("dataset", ["P2"], "LongDocs"),
            ("metric", [], "F1"),  # no citation -> unknown
            ("result", ["P7"], "41.2 F1"),  # invalid label -> unknown
            ("limitations", ["P2"], "unknown"),
        )
    ]
    body = env.client.post(f"/api/v1/papers/{env.a}/extraction").json()
    fields = {f["field"]: f for f in body["result"]["fields"]}
    assert list(fields) == ["task", "method", "dataset", "metric", "result", "limitations"]
    assert fields["task"]["status"] == "found" and fields["task"]["citations"] == [
        {"label": "P1", "valid": True}
    ]
    assert fields["dataset"]["value"] == "LongDocs"
    for name in ("method", "metric", "result", "limitations"):
        assert (fields[name]["status"], fields[name]["value"], fields[name]["citations"]) == (
            "unknown",
            "unknown",
            [],
        )


def test_synthesis_draws_evidence_from_every_selected_paper(env: Env) -> None:
    env.provider.responses = [answer_json(("Both papers propose a method.", ["P1", "P3"]))]
    body = env.client.post(
        "/api/v1/synthesis", json={"topic": "proposed method", "paper_ids": [env.a, env.b]}
    ).json()
    assert body["status"] == "completed" and body["topic"] == "proposed method"
    assert {e["paper_id"] for e in body["evidence"]} == {env.a, env.b}
    prompt = env.provider.requests[0].prompt
    assert 'paper="Sparse Attention Paper"' in prompt and 'paper="Graph Molecule Paper"' in prompt


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"topic": "x", "paper_ids": ["A"]}, 422),
        ({"topic": "   ", "paper_ids": ["A", "B"]}, 422),
        ({"topic": "x", "paper_ids": ["A", str(uuid.uuid4())]}, 404),
    ],
)
def test_synthesis_validation(env: Env, body: dict[str, Any], status: int) -> None:
    names: list[str] = body["paper_ids"]
    ids = [env.a if p == "A" else env.b if p == "B" else p for p in names]
    response = env.client.post("/api/v1/synthesis", json={**body, "paper_ids": ids})
    assert response.status_code == status


def test_compare_extracts_missing_and_flags_different_datasets(env: Env) -> None:
    env.provider.responses = [
        fields_json(("dataset", ["P2"], "LongDocs"), ("result", ["P2"], "41.2 F1 on LongDocs")),
        fields_json(("dataset", ["P2"], "MolSet"), ("result", ["P2"], "0.81 AUC on MolSet")),
    ]
    body = env.client.post("/api/v1/compare", json={"paper_ids": [env.a, env.b]}).json()
    assert [p["title"] for p in body["papers"]] == [
        "Sparse Attention Paper",
        "Graph Molecule Paper",
    ]
    assert body["papers"][0]["fields"]["dataset"]["value"] == "LongDocs"
    assert body["papers"][1]["fields"]["result"]["value"] == "0.81 AUC on MolSet"
    assert any("not directly comparable" in c for c in body["caveats"])
    assert len(env.provider.requests) == 2

    again = env.client.post(
        "/api/v1/compare", json={"paper_ids": [env.a, env.b], "extract_missing": False}
    ).json()
    assert len(env.provider.requests) == 2  # stored extractions reused
    assert again["papers"][0]["analysis_id"] == body["papers"][0]["analysis_id"]


def test_generation_failure_is_explicit_and_recorded(env: Env) -> None:
    env.provider.error = DependencyUnavailableError("Ollama is not reachable")
    response = env.client.post(f"/api/v1/papers/{env.a}/summary")
    assert response.status_code == 503
    with env.sessions() as session:
        stored = session.scalars(select(Analysis)).one()
    assert stored.status == "error" and stored.reason == "Ollama is not reachable"
    assert env.client.get(f"/api/v1/papers/{env.a}/latest/summary").status_code == 404


def test_unknown_paper_and_analysis_return_404(env: Env) -> None:
    missing = str(uuid.uuid4())
    assert env.client.post(f"/api/v1/papers/{missing}/summary").status_code == 404
    assert env.client.get(f"/api/v1/analyses/{missing}").status_code == 404
