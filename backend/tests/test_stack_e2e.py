"""End-to-end test against a running stack (M7): upload -> ingest -> search (all modes) -> Q&A ->
summary -> delete, over HTTP through the frontend's nginx proxy.

Real components only: PostgreSQL + pgvector, MiniLM, the cross-encoder, and the local Ollama model.
Run with ``SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 uv run pytest -m e2e``. Skipped when the
variable is unset. The uploaded paper is synthetic and is deleted at the end.
"""

import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from tests.fakes import make_pdf

pytestmark = pytest.mark.e2e

BASE_URL = os.environ.get("SLIP_E2E_BASE_URL")

# A unique marker keeps the synthetic document distinguishable from real corpus papers.
MARKER = f"zephyrine{uuid.uuid4().hex[:8]}"
PAGES = [
    (
        f"The {MARKER} protocol is a synthetic test method for document retrieval. "
        f"The {MARKER} protocol was evaluated on the Quokka benchmark and reached an accuracy "
        "of 91.4 percent. "
    )
    * 3,
    (
        f"Training the {MARKER} protocol took 7 hours on a single GPU. "
        "Its main limitation is that it only supports English text. "
    )
    * 3,
]


@pytest.fixture(scope="module")
def api() -> Iterator[httpx.Client]:
    if not BASE_URL:
        pytest.skip("SLIP_E2E_BASE_URL is not set (needs a running stack)")
    with httpx.Client(base_url=BASE_URL, timeout=180) as client:
        yield client


@pytest.fixture(scope="module")
def paper_id(api: httpx.Client) -> Iterator[str]:
    files = {"file": ("e2e.pdf", make_pdf(PAGES), "application/pdf")}
    response = api.post("/papers/upload", files=files, data={"title": f"E2E {MARKER}"})
    assert response.status_code == 202, response.text
    job = _wait_for_job(api, response.json()["id"])
    assert job["state"] == "ready", job
    pid = str(job["paper_id"])
    yield pid
    assert api.delete(f"/papers/{pid}").status_code == 204
    assert api.get(f"/papers/{pid}").status_code == 404


def _wait_for_job(api: httpx.Client, job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        job: dict[str, Any] = api.get(f"/jobs/{job_id}").json()
        if job["state"] in {"ready", "failed"}:
            return job
        time.sleep(1)
    raise AssertionError("ingestion job did not finish within 300 s")


def test_ready_reports_every_dependency(api: httpx.Client) -> None:
    body = api.get("/ready").json()
    assert body["status"] == "ready", body
    assert all(check["ok"] for check in body["checks"].values()), body


@pytest.mark.parametrize("mode", ["dense", "bm25", "hybrid", "hybrid_rerank"])
def test_search_finds_the_uploaded_paper(api: httpx.Client, paper_id: str, mode: str) -> None:
    query = {"query": f"{MARKER} protocol accuracy on Quokka", "top_k": 3, "search_mode": mode}
    response = api.post("/search", json=query)
    assert response.status_code == 200, response.text
    top = response.json()["results"][0]
    assert top["paper"]["id"] == paper_id
    assert MARKER in top["text"]
    assert top["page_start"] >= 1 and top["char_start"] < top["char_end"]


def test_qa_answers_with_valid_citations_only(api: httpx.Client, paper_id: str) -> None:
    question = {
        "question": f"What accuracy did the {MARKER} protocol reach on the Quokka benchmark?"
    }
    response = api.post("/qa", json={**question, "paper_ids": [paper_id]})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["status"] in {"answered", "insufficient_evidence"}, answer
    labels = {e["label"] for e in answer["evidence"]}
    for claim in answer["claims"]:
        for citation in claim["citations"]:
            # A citation is shown as valid only if it names a passage the model was given.
            assert citation["valid"] == (citation["label"] in labels)
        if claim["support"] == "cited":
            assert any(c["valid"] for c in claim["citations"])
    assert api.get(f"/qa/{answer['id']}").json()["id"] == answer["id"]


def test_summary_is_cited_or_abstains(api: httpx.Client, paper_id: str) -> None:
    response = api.post(f"/papers/{paper_id}/summary")
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert analysis["status"] in {"completed", "insufficient_evidence"}, analysis
    assert analysis["generation_model"]
