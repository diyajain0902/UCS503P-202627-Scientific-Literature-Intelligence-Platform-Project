"""Persisted semantic search and the HTTP vertical slice (FR-08, AC-08.1-AC-08.4, IR-05)."""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.ingestion.chunking import ChunkingConfig
from app.main import create_app
from tests.fakes import FakeArxiv, make_pdf, make_test_container, synthetic_metadata

pytestmark = pytest.mark.integration

ATTENTION = [
    "Multi head self attention computes attention weights between all token pairs. " * 3,
    "Layer normalization and residual connections stabilise transformer training. " * 3,
]
GRAPHS = [
    "Graph neural networks aggregate messages from neighbouring nodes in a graph. " * 3,
    "Node classification benchmarks include citation networks such as Cora. " * 3,
]


@pytest.fixture
def client(
    sessions: sessionmaker[Session], database_url: str, tmp_path: Path
) -> Iterator[TestClient]:
    settings = Settings(database_url=database_url, ollama_base_url="http://127.0.0.1:1")
    arxiv = FakeArxiv()
    arxiv.add(synthetic_metadata("2101.00001", title="Attention Paper"), make_pdf(ATTENTION))
    arxiv.add(synthetic_metadata("2101.00002", title="Graph Paper"), make_pdf(GRAPHS))
    container = make_test_container(
        settings, sessions, tmp_path, arxiv=arxiv, chunking=ChunkingConfig(24, 4)
    )
    with TestClient(create_app(container=container)) as test_client:
        yield test_client
    container.close()


def _import(client: TestClient, arxiv_id: str) -> dict[str, object]:
    response = client.post("/api/v1/papers/arxiv", json={"arxiv_id": arxiv_id})
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job: dict[str, object] = client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] in {"ready", "failed"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_vertical_slice_import_list_search(client: TestClient) -> None:
    assert _import(client, "2101.00001")["state"] == "ready"
    assert _import(client, "2101.00002")["state"] == "ready"

    papers = client.get("/api/v1/papers").json()
    assert papers["total"] == 2
    assert {p["title"] for p in papers["items"]} == {"Attention Paper", "Graph Paper"}
    assert all(p["page_count"] == 2 and p["chunk_count"] > 0 for p in papers["items"])

    response = client.post(
        "/api/v1/search", json={"query": "graph neural networks nodes", "top_k": 3}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["embedding_model"] == "test-hashing-embedder"
    results = body["results"]
    assert len(results) == 3
    assert results[0]["paper"]["title"] == "Graph Paper"
    assert results[0]["page_start"] == 1
    assert [r["rank"] for r in results] == [1, 2, 3]
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert "graph" in results[0]["text"].lower()


def test_search_filters_by_paper_and_is_deterministic(client: TestClient) -> None:
    _import(client, "2101.00001")
    _import(client, "2101.00002")
    papers = {p["title"]: p["id"] for p in client.get("/api/v1/papers").json()["items"]}

    body = {"query": "graph neural networks", "top_k": 50, "paper_ids": [papers["Attention Paper"]]}
    filtered = client.post("/api/v1/search", json=body).json()["results"]
    assert filtered and all(r["paper"]["title"] == "Attention Paper" for r in filtered)

    first = client.post("/api/v1/search", json={"query": "attention weights"}).json()["results"]
    second = client.post("/api/v1/search", json={"query": "attention weights"}).json()["results"]
    assert [r["chunk_id"] for r in first] == [r["chunk_id"] for r in second]


def test_search_on_empty_corpus_returns_no_results(client: TestClient) -> None:
    response = client.post("/api/v1/search", json={"query": "anything"})
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_unknown_ids_return_404_envelope(client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    for path in (f"/api/v1/papers/{missing}", f"/api/v1/jobs/{missing}"):
        response = client.get(path)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


def test_ready_with_database_and_without_ollama(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200  # Ollama is not required for search (NFR-16)
    checks = response.json()["checks"]
    assert checks["database"]["ok"] is True and "pgvector" in checks["database"]["detail"]
    assert checks["ollama"]["ok"] is False


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_every_search_mode_reports_cosine_scores(client: TestClient, mode: str) -> None:
    """Regression (M6): ``score`` is the cosine similarity in every mode, so ``qa_min_score``
    keeps its calibrated meaning; the mode's own ordering score is ``rank_score`` (FR-24)."""
    _import(client, "2101.00001")
    _import(client, "2101.00002")
    query = {"query": "graph neural networks nodes", "top_k": 5, "search_mode": mode}
    results = client.post("/api/v1/search", json=query).json()["results"]

    assert results
    assert results[0]["paper"]["title"] == "Graph Paper"
    assert all(-1.0 <= r["score"] <= 1.0 for r in results)
    rank_scores = [r["rank_score"] for r in results]
    if mode == "dense":
        assert rank_scores == [None] * len(results)
    else:
        # The test container has no reranker, so hybrid_rerank falls back to RRF order.
        assert rank_scores == sorted(rank_scores, reverse=True)
    if mode == "bm25":
        terms = ("graph", "neural", "node", "network")  # English stems of the query terms
        assert all(any(t in r["text"].lower() for t in terms) for r in results)


def test_bm25_uses_the_stored_tsvector_index(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        indexdef = session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_text_tsv'")
        ).scalar_one()
        generated = session.execute(
            text(
                "SELECT is_generated FROM information_schema.columns "
                "WHERE table_name = 'chunks' AND column_name = 'text_tsv'"
            )
        ).scalar_one()
    assert "gin (text_tsv)" in indexdef
    assert generated == "ALWAYS"
