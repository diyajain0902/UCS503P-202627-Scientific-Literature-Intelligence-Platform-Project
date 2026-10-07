"""Migrations and database constraints (FR-07, AC-07.1, AC-07.2, AC-07.3)."""

import uuid

import pytest
from alembic import command
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Chunk, Document, IngestionJob, Paper
from tests.conftest import alembic_config

pytestmark = pytest.mark.integration

UNIT = [1.0] + [0.0] * 383


def _paper(arxiv_id: str = "2101.00001") -> Paper:
    return Paper(
        source="arxiv", arxiv_id=arxiv_id, arxiv_version=1, title="T", authors=[], categories=[]
    )


def _document(paper: Paper, sha: str = "a" * 64) -> Document:
    return Document(
        paper=paper,
        sha256=sha,
        storage_key=f"{sha}.pdf",
        byte_size=10,
        page_count=1,
        extractor_version="x",
        chunker_version="y",
        embedding_model="z",
    )


def _chunk(document_id: uuid.UUID, **overrides: object) -> Chunk:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "document_id": document_id,
        "ordinal": 0,
        "page_start": 1,
        "page_end": 1,
        "char_start": 0,
        "char_end": 5,
        "token_count": 1,
        "text": "hello",
        "embedding": UNIT,
    }
    values.update(overrides)
    return Chunk(**values)


def test_schema_has_tables_and_hnsw_index(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    assert {"papers", "documents", "chunks", "ingestion_jobs"} <= set(inspector.get_table_names())
    with migrated_engine.connect() as connection:
        indexdef = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_chunks_embedding_hnsw'")
        ).scalar_one()
    assert "hnsw" in indexdef and "vector_cosine_ops" in indexdef


def test_orm_models_match_migrations(database_url: str, migrated_engine: Engine) -> None:
    command.check(alembic_config(database_url))  # raises if autogenerate would detect drift


def test_downgrade_and_upgrade_roundtrip(database_url: str, migrated_engine: Engine) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, "base")
    assert "papers" not in inspect(migrated_engine).get_table_names()
    command.upgrade(config, "head")
    assert "papers" in inspect(migrated_engine).get_table_names()


def test_duplicate_arxiv_id_rejected(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add_all([_paper(), _paper()])
        with pytest.raises(IntegrityError, match="uq_papers_arxiv_id"):
            session.commit()


def test_arxiv_source_requires_arxiv_id(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add(Paper(source="arxiv", arxiv_id=None, title="T", authors=[], categories=[]))
        with pytest.raises(IntegrityError, match="ck_papers_arxiv_id_matches_source"):
            session.commit()


def test_embedding_dimension_enforced(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        document = _document(_paper())
        session.add(document)
        session.flush()
        session.add(_chunk(document.id, embedding=[0.1] * 383))
        with pytest.raises(DBAPIError, match="expected 384 dimensions"):
            session.commit()


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"page_start": 2, "page_end": 1}, "ck_chunks_pages"),
        ({"page_start": 0, "page_end": 1}, "ck_chunks_pages"),
        ({"char_start": 5, "char_end": 5}, "ck_chunks_chars"),
        ({"token_count": 0}, "ck_chunks_token_count"),
    ],
)
def test_chunk_checks(
    sessions: sessionmaker[Session], overrides: dict[str, object], constraint: str
) -> None:
    with sessions() as session:
        document = _document(_paper())
        session.add(document)
        session.flush()
        session.add(_chunk(document.id, **overrides))
        with pytest.raises(IntegrityError, match=constraint):
            session.commit()


def test_failed_job_requires_error_and_vice_versa(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add(IngestionJob(kind="arxiv_import", state="failed", source_ref="x", attempts=1))
        with pytest.raises(IntegrityError, match="ck_ingestion_jobs_error_iff_failed"):
            session.commit()


def test_only_one_active_job_per_source(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.add(IngestionJob(kind="arxiv_import", state="ready", source_ref="x", attempts=1))
        session.add(IngestionJob(kind="arxiv_import", state="queued", source_ref="x", attempts=0))
        session.commit()  # one finished + one active is fine
        session.add(IngestionJob(kind="arxiv_import", state="fetching", source_ref="x", attempts=0))
        with pytest.raises(IntegrityError, match="uq_ingestion_jobs_active_source"):
            session.commit()


def test_deleting_paper_cascades_to_documents_and_chunks(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        paper = _paper()
        document = _document(paper)
        session.add(document)
        session.flush()
        session.add(_chunk(document.id))
        session.add(
            IngestionJob(
                kind="arxiv_import", state="ready", source_ref="x", attempts=1, paper_id=paper.id
            )
        )
        session.commit()
        session.delete(paper)
        session.commit()
        assert session.scalars(select(Document)).all() == []
        assert session.scalars(select(Chunk)).all() == []
        assert session.scalars(select(IngestionJob)).all() == []
