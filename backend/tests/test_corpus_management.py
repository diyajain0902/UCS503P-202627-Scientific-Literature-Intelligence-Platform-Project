"""Corpus management through the HTTP API on real PostgreSQL (M4).

Covers AC-03.1-AC-03.5, AC-07.3, AC-16.1, AC-16.2, AC-17.2, FR-01 (search), FR-22, FR-23.
The arXiv source, embedder, and LLM are controlled doubles (see tests/fakes.py).
"""

import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.container import Container
from app.core.config import Settings
from app.db.models import Chunk, Document
from app.ingestion.chunking import ChunkingConfig
from app.main import create_app
from tests.fakes import (
    FakeArxiv,
    answer_json,
    make_pdf,
    make_test_container,
    synthetic_metadata,
)

pytestmark = pytest.mark.integration

TEXT = ["Uploaded study of sparse attention patterns in long documents. " * 4]


@dataclass
class Env:
    client: TestClient
    container: Container
    sessions: sessionmaker[Session]
    storage: Path
    arxiv: FakeArxiv


@pytest.fixture
def env(sessions: sessionmaker[Session], database_url: str, tmp_path: Path) -> Iterator[Env]:
    settings = Settings(
        database_url=database_url,
        ollama_base_url="http://127.0.0.1:1",
        max_pdf_bytes=200_000,
        max_pdf_pages=5,
        qa_min_score=0.0,
    )
    arxiv = FakeArxiv()
    arxiv.add(synthetic_metadata("2101.00001", title="Graph Transformers"), make_pdf(TEXT))
    storage = tmp_path / "storage"
    container = make_test_container(
        settings, sessions, storage, arxiv=arxiv, chunking=ChunkingConfig(32, 4)
    )
    with TestClient(create_app(container=container)) as client:
        yield Env(client, container, sessions, storage, arxiv)
    container.close()


def _wait(env: Env, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job: dict[str, object] = env.client.get(f"/api/v1/jobs/{job_id}").json()
        if job["state"] in {"ready", "failed"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def _upload(env: Env, data: bytes, name: str = "paper.pdf", **form: str) -> dict[str, object]:
    response = env.client.post(
        "/api/v1/papers/upload", files={"file": (name, data, "application/pdf")}, data=form
    )
    body: dict[str, object] = response.json()
    body["_status"] = response.status_code
    return body


def _files(env: Env) -> list[str]:
    return sorted(p.name for p in env.storage.iterdir()) if env.storage.exists() else []


# ---- upload (FR-03) -----------------------------------------------------------------------------


def test_upload_is_ingested_and_searchable(env: Env) -> None:
    job = _upload(env, make_pdf(TEXT), title="  My   Sparse Attention Study ")
    assert job["_status"] == 202 and job["kind"] == "pdf_upload"
    assert job["display_name"] == "My Sparse Attention Study"
    done = _wait(env, str(job["id"]))
    assert done["state"] == "ready", done

    paper = env.client.get(f"/api/v1/papers/{done['paper_id']}").json()
    assert paper["source"] == "upload" and paper["arxiv_id"] is None
    assert paper["title"] == "My Sparse Attention Study" and paper["chunk_count"] > 0
    hits = env.client.post("/api/v1/search", json={"query": "sparse attention"}).json()["results"]
    assert hits and hits[0]["paper"]["id"] == paper["id"]


def test_duplicate_upload_is_rejected_with_conflict(env: Env) -> None:
    data = make_pdf(TEXT)
    _wait(env, str(_upload(env, data)["id"]))
    again = _upload(env, data, name="copy.pdf")
    assert again["_status"] == 409 and again["error"]["code"] == "conflict"  # type: ignore[index]


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        (b"<html>not a pdf</html>", "not a PDF"),
        (b"%PDF-1.7\n" + b"\x00garbage" * 50, "corrupt"),
        (make_pdf(["x " * 30] * 6), "limit is 5"),
        (b"%PDF-" + b"0" * 250_000, "larger than"),
    ],
    ids=["not-pdf", "corrupt", "too-many-pages", "too-large"],
)
def test_invalid_uploads_rejected_before_any_job(env: Env, data: bytes, fragment: str) -> None:
    result = _upload(env, data)
    assert result["_status"] == 422
    assert fragment in result["error"]["message"]  # type: ignore[index]
    assert env.client.get("/api/v1/jobs").json() == []
    assert _files(env) == []


def test_encrypted_upload_rejected(env: Env) -> None:
    source = pymupdf.open("pdf", make_pdf(TEXT))
    data = source.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        user_pw="secret",
        owner_pw="owner",
    )
    result = _upload(env, data)
    assert result["_status"] == 422 and "encrypted" in result["error"]["message"]  # type: ignore[index]


def test_user_file_name_never_becomes_a_path(env: Env) -> None:
    job = _upload(env, make_pdf(TEXT), name="../../../etc/passwd.pdf")
    _wait(env, str(job["id"]))
    files = _files(env)
    assert len(files) == 1 and len(files[0]) == 68 and files[0].endswith(".pdf")  # sha256 + .pdf
    assert job["display_name"] == "../../../etc/passwd.pdf"  # kept only as a label


def test_scanned_upload_fails_job_and_discards_file(env: Env) -> None:
    blank = pymupdf.open()
    blank.new_page()
    job = _upload(env, blank.tobytes())
    if job["_status"] == 202:  # structural checks pass; text check happens in the job
        done = _wait(env, str(job["id"]))
        assert done["state"] == "failed" and "OCR is not supported" in str(done["error"])
    assert _files(env) == []


# ---- jobs and retry (FR-17) ---------------------------------------------------------------------


def test_failed_job_can_be_retried(env: Env) -> None:
    env.arxiv.papers.pop("2101.00001")
    first = env.client.post("/api/v1/papers/arxiv", json={"arxiv_id": "2101.00001"}).json()
    assert _wait(env, first["id"])["state"] == "failed"

    env.arxiv.add(synthetic_metadata("2101.00001"), make_pdf(TEXT))
    retried = env.client.post(f"/api/v1/jobs/{first['id']}/retry")
    assert retried.status_code == 202
    assert _wait(env, retried.json()["id"])["state"] == "ready"

    again = env.client.post(f"/api/v1/jobs/{retried.json()['id']}/retry")
    assert again.status_code == 409  # only failed jobs can be retried
    jobs = env.client.get("/api/v1/jobs?limit=10").json()
    assert [j["state"] for j in jobs] == ["ready", "failed"]
    assert [j["state"] for j in env.client.get("/api/v1/jobs?state=failed").json()] == ["failed"]


# ---- corpus browsing and deletion (FR-16) -------------------------------------------------------


def test_filters_and_categories(env: Env) -> None:
    _wait(
        env, env.client.post("/api/v1/papers/arxiv", json={"arxiv_id": "2101.00001"}).json()["id"]
    )
    _wait(env, str(_upload(env, make_pdf(TEXT), title="Upload One")["id"]))

    def titles(query: str) -> list[str]:
        return [p["title"] for p in env.client.get(f"/api/v1/papers?{query}").json()["items"]]

    assert set(titles("")) == {"Graph Transformers", "Upload One"}
    assert titles("source=upload") == ["Upload One"]
    assert titles("source=arxiv") == ["Graph Transformers"]
    assert titles("category=cs.CL") == ["Graph Transformers"]
    assert titles("year=2020") == ["Graph Transformers"]
    assert titles("year=1999") == []
    assert titles("q=graph") == ["Graph Transformers"]
    assert titles("q=%25") == []  # LIKE wildcard is escaped
    assert env.client.get("/api/v1/papers?source=other").status_code == 422
    assert env.client.get("/api/v1/categories").json() == ["cs.CL"]


def test_delete_removes_paper_chunks_file_and_keeps_history(env: Env) -> None:
    done = _wait(env, str(_upload(env, make_pdf(TEXT))["id"]))
    paper_id = done["paper_id"]
    provider = env.container.qa._provider
    provider.responses = [answer_json(("Sparse attention is studied.", ["P1"]))]  # type: ignore[attr-defined]
    answer = env.client.post("/api/v1/qa", json={"question": "What is studied?"}).json()
    assert answer["status"] == "answered"

    assert env.client.delete(f"/api/v1/papers/{paper_id}").status_code == 204
    assert env.client.get(f"/api/v1/papers/{paper_id}").status_code == 404
    assert env.client.delete(f"/api/v1/papers/{paper_id}").status_code == 404
    with env.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0
        assert session.scalar(select(func.count()).select_from(Document)) == 0
    assert _files(env) == []
    history = env.client.get(f"/api/v1/qa/{answer['id']}").json()
    assert history["evidence"][0]["chunk_id"] is None and history["evidence"][0]["text"]


# ---- discovery, stats, settings (FR-01, FR-22, FR-23) -------------------------------------------


def test_arxiv_search_marks_imported_papers(env: Env) -> None:
    before = env.client.get("/api/v1/arxiv/search?q=graph").json()
    assert [(r["arxiv_id"], r["stored_version"]) for r in before] == [("2101.00001", None)]
    _wait(
        env, env.client.post("/api/v1/papers/arxiv", json={"arxiv_id": "2101.00001"}).json()["id"]
    )
    after = env.client.get("/api/v1/arxiv/search?q=graph").json()
    assert after[0]["stored_version"] == 1
    assert env.client.get("/api/v1/arxiv/search?q=").status_code == 422


def test_stats_and_settings(env: Env) -> None:
    _wait(env, str(_upload(env, make_pdf(TEXT))["id"]))
    stats = env.client.get("/api/v1/stats").json()
    assert stats["papers"] == 1 and stats["papers_by_source"] == {"upload": 1}
    assert stats["chunks"] > 0 and stats["pages"] == 1
    assert stats["jobs_by_state"] == {"ready": 1}

    settings = env.client.get("/api/v1/settings").json()
    assert settings["embedding_dimension"] == 384 and settings["max_pdf_pages"] == 5
    serialized = str(settings).lower()
    assert "postgres" not in serialized and "password" not in serialized
