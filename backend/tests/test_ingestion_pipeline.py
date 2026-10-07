"""Ingestion pipeline against real PostgreSQL + pgvector, with controlled arXiv/embedder doubles.

Covers AC-02.1, AC-02.2, AC-04.2, AC-05.3, AC-05.4, AC-17.1, AC-17.2.
"""

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Chunk, Document, IngestionJob, Paper
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.storage import FileStore
from app.services.ingestion import IngestionService
from app.services.jobs import INTERRUPTED_MESSAGE, fail_interrupted_jobs
from tests.fakes import (
    FakeArxiv,
    HashingEmbedder,
    WhitespaceTokenizer,
    make_pdf,
    synthetic_metadata,
)

pytestmark = pytest.mark.integration

PAGES = [
    "Self attention lets every token attend to every other token in the sequence. " * 4,
    "Positional encodings inject order information into the transformer model. " * 4,
]


class Harness:
    def __init__(self, sessions: sessionmaker[Session], tmp_path: Path) -> None:
        self.sessions = sessions
        self.arxiv = FakeArxiv()
        self.embedder = HashingEmbedder()
        self.storage_dir = tmp_path / "storage"
        self.service = IngestionService(
            sessions,
            self.arxiv,
            self.embedder,
            WhitespaceTokenizer,
            FileStore(self.storage_dir),
            ChunkingConfig(window_tokens=32, overlap_tokens=5),
            max_pdf_bytes=5 * 1024 * 1024,
            max_pdf_pages=10,
        )

    def run(self, arxiv_id: str) -> IngestionJob:
        job, created = self.service.request_arxiv_import(arxiv_id)
        assert created
        self.service.run_job(job.id)
        with self.sessions() as session:
            refreshed = session.get(IngestionJob, job.id)
            assert refreshed is not None
            return refreshed

    def count(self, model: type[object]) -> int:
        with self.sessions() as session:
            return int(session.scalar(select(func.count()).select_from(model)) or 0)

    def chunk_ids(self) -> list[str]:
        with self.sessions() as session:
            return [str(i) for i in session.scalars(select(Chunk.id).order_by(Chunk.ordinal))]

    def stored_files(self) -> list[str]:
        return sorted(p.name for p in self.storage_dir.iterdir())


@pytest.fixture
def harness(sessions: sessionmaker[Session], tmp_path: Path) -> Harness:
    return Harness(sessions, tmp_path)


def test_import_reaches_ready_with_provenance(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00001", title="Attention Study"), make_pdf(PAGES))
    job = harness.run("2101.00001")

    assert job.state == "ready" and job.error is None and job.attempts == 1
    assert job.finished_at is not None
    with harness.sessions() as session:
        paper = session.scalars(select(Paper)).one()
        assert (paper.arxiv_id, paper.arxiv_version, paper.title) == (
            "2101.00001",
            1,
            "Attention Study",
        )
        assert job.paper_id == paper.id
        document = session.scalars(select(Document)).one()
        assert document.page_count == 2
        assert document.chunker_version == "tokwin-v1|test-whitespace|w32|o5"
        assert document.embedding_model == "test-hashing-embedder"
        chunks = session.scalars(select(Chunk).order_by(Chunk.ordinal)).all()
    assert len(chunks) > 2
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    assert chunks[0].page_start == 1 and chunks[-1].page_end == 2
    assert any(c.page_start == 1 and c.page_end == 2 for c in chunks)  # a chunk spans the boundary
    assert all(len(c.embedding) == 384 for c in chunks)
    assert harness.stored_files() == [f"{document.sha256}.pdf"]


def test_reimport_same_version_is_idempotent(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00001"), make_pdf(PAGES))
    harness.run("2101.00001")
    ids_before, embed_calls = harness.chunk_ids(), harness.embedder.calls

    second = harness.run("2101.00001v1")
    assert second.state == "ready"
    assert harness.count(Paper) == 1 and harness.count(Document) == 1
    assert harness.chunk_ids() == ids_before
    assert harness.embedder.calls == embed_calls  # no re-embedding
    assert harness.arxiv.downloads == 1  # no re-download


def test_new_version_replaces_document_and_old_file(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00001", version=1), make_pdf(PAGES))
    harness.run("2101.00001")
    old_files = harness.stored_files()

    harness.arxiv.add(
        synthetic_metadata("2101.00001", version=2), make_pdf([*PAGES, "Revised conclusion. " * 10])
    )
    assert harness.run("2101.00001").state == "ready"
    with harness.sessions() as session:
        paper = session.scalars(select(Paper)).one()
        document = session.scalars(select(Document)).one()
    assert paper.arxiv_version == 2 and document.page_count == 3
    assert harness.count(Paper) == 1
    assert harness.stored_files() == [f"{document.sha256}.pdf"] != old_files


def test_rejected_pdf_fails_job_without_partial_data(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00002"), b"<html>arXiv error page</html>")
    job = harness.run("2101.00002")
    assert job.state == "failed"
    assert job.error == "File is not a PDF (missing %PDF- header)"
    assert harness.count(Paper) == 0 and harness.count(Chunk) == 0
    assert not harness.storage_dir.exists() or harness.stored_files() == []


def test_unknown_paper_fails_with_actionable_message(harness: Harness) -> None:
    job = harness.run("2101.09999")
    assert job.state == "failed"
    assert job.error is not None and "no paper with identifier 2101.09999" in job.error


def test_unexpected_crash_is_recorded_and_rolls_back(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00001"), make_pdf(PAGES))

    def broken_embed(texts: list[str]) -> list[list[float]]:
        raise RuntimeError("simulated failure")

    harness.embedder.embed = broken_embed  # type: ignore[method-assign]
    job = harness.run("2101.00001")
    assert job.state == "failed"
    assert job.error == "Unexpected internal error during ingestion; see server logs."
    assert harness.count(Paper) == 0 and harness.count(Chunk) == 0


def test_failed_job_can_be_retried(harness: Harness) -> None:
    harness.arxiv.add(synthetic_metadata("2101.00003"), b"not a pdf")
    assert harness.run("2101.00003").state == "failed"
    harness.arxiv.add(synthetic_metadata("2101.00003"), make_pdf(PAGES))
    assert harness.run("2101.00003").state == "ready"
    assert harness.count(Paper) == 1


def test_same_pdf_under_two_ids_is_rejected(harness: Harness) -> None:
    pdf = make_pdf(PAGES)
    harness.arxiv.add(synthetic_metadata("2101.00001"), pdf)
    harness.arxiv.add(synthetic_metadata("2101.00002"), pdf)
    harness.run("2101.00001")
    job = harness.run("2101.00002")
    assert job.state == "failed"
    assert job.error == "This PDF is already stored for another paper"
    assert len(harness.stored_files()) == 1  # the first paper's file is kept


def test_concurrent_request_returns_in_flight_job(harness: Harness) -> None:
    first, created_first = harness.service.request_arxiv_import("2101.00001")
    second, created_second = harness.service.request_arxiv_import("2101.00001")
    assert created_first and not created_second
    assert first.id == second.id


def test_interrupted_jobs_marked_failed_on_startup(harness: Harness) -> None:
    job, _ = harness.service.request_arxiv_import("2101.00001")
    assert fail_interrupted_jobs(harness.sessions) == 1
    with harness.sessions() as session:
        refreshed = session.get(IngestionJob, job.id)
    assert refreshed is not None
    assert (refreshed.state, refreshed.error) == ("failed", INTERRUPTED_MESSAGE)
