"""API behaviour that must hold without a database: validation, errors, readiness."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.container import Container
from app.core.config import Settings
from app.db.session import make_engine, make_session_factory
from app.ingestion.chunking import ChunkingConfig
from app.ingestion.storage import FileStore
from app.main import create_app
from app.services.corpus import CorpusService
from app.services.ingestion import IngestionService
from app.services.jobs import JobRunner
from app.services.search import SearchService
from tests.fakes import FakeArxiv, HashingEmbedder, WhitespaceTokenizer

# Port 1 on localhost refuses connections immediately: any accidental DB access fails fast.
UNREACHABLE_DB = "postgresql+psycopg://nobody:nothing@127.0.0.1:1/none?connect_timeout=1"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        database_url=UNREACHABLE_DB,
        ollama_base_url="http://127.0.0.1:1",
        search_max_top_k=20,
        search_max_query_chars=50,
    )
    sessions = make_session_factory(make_engine(settings.database_url))
    embedder = HashingEmbedder()
    ingestion = IngestionService(
        sessions,
        FakeArxiv(),
        embedder,
        WhitespaceTokenizer,
        FileStore(tmp_path),
        ChunkingConfig(256, 38),
        1024,
        10,
    )
    container = Container(
        settings=settings,
        session_factory=sessions,
        embedder=embedder,
        ingestion=ingestion,
        search=SearchService(sessions, embedder, settings.search_max_top_k),
        corpus=CorpusService(sessions),
        runner=JobRunner(1, ingestion.run_job),
    )
    with TestClient(create_app(container=container)) as test_client:
        yield test_client
    container.close()


def _assert_error(response_json: dict[str, dict[str, str]], code: str) -> None:
    assert set(response_json) == {"error"}
    assert response_json["error"]["code"] == code
    assert response_json["error"]["message"]


@pytest.mark.parametrize("arxiv_id", ["not-an-id", "../../etc/passwd", "1706.037"])
def test_invalid_arxiv_id_rejected_before_any_work(client: TestClient, arxiv_id: str) -> None:
    response = client.post("/api/v1/papers/arxiv", json={"arxiv_id": arxiv_id})
    assert response.status_code == 422
    _assert_error(response.json(), "invalid_input")


@pytest.mark.parametrize(
    ("body", "fragment"),
    [
        ({"query": ""}, "query"),
        ({"query": "   "}, "must contain text"),
        ({"query": "x" * 51}, "at most 50"),
        ({"query": "ok", "top_k": 0}, "top_k"),
        ({"query": "ok", "top_k": 21}, "between 1 and 20"),
        ({"query": "ok", "paper_ids": ["not-a-uuid"]}, "paper_ids"),
    ],
)
def test_search_input_bounds(client: TestClient, body: dict[str, object], fragment: str) -> None:
    response = client.post("/api/v1/search", json=body)
    assert response.status_code == 422
    _assert_error(response.json(), "invalid_input")
    assert fragment in response.json()["error"]["message"]


def test_pagination_bounds(client: TestClient) -> None:
    assert client.get("/api/v1/papers?limit=0").status_code == 422
    assert client.get("/api/v1/papers?limit=101").status_code == 422
    assert client.get("/api/v1/papers?offset=-1").status_code == 422


def test_ready_reports_each_dependency_and_fails_without_database(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"]["ok"] is False
    assert body["checks"]["embedding_model"]["ok"] is True
    assert body["checks"]["ollama"]["ok"] is False


def test_request_id_header(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert len(response.headers["X-Request-ID"]) == 32
