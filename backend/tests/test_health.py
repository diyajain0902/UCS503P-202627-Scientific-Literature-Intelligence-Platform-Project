from fastapi.testclient import TestClient

from app import __version__
from app.core.config import Settings
from app.main import create_app


def test_health_reports_ok_and_version() -> None:
    client = TestClient(create_app(Settings()))
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_openapi_schema_is_versioned() -> None:
    client = TestClient(create_app(Settings()))
    assert client.get("/api/v1/openapi.json").status_code == 200


def test_cors_allows_only_configured_origin() -> None:
    client = TestClient(create_app(Settings(cors_origins=["http://allowed.test"])))
    allowed = client.get("/api/v1/health", headers={"Origin": "http://allowed.test"})
    denied = client.get("/api/v1/health", headers={"Origin": "http://evil.test"})
    assert allowed.headers.get("access-control-allow-origin") == "http://allowed.test"
    assert "access-control-allow-origin" not in denied.headers
