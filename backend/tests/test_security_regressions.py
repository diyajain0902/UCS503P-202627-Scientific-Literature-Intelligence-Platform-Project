"""Security regressions from the MVP security audit (step 5b, docs/security/mvp-security-audit.md).

No database or model needed: the error handlers are exercised on a minimal app.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import INTERNAL_ERROR_MESSAGE, NotFoundError, register_error_handlers

INTERNAL_DETAIL = "postgresql+psycopg://slip:fake-pw-not-real@db/slip at /app/data/storage/x.pdf"


def _app() -> FastAPI:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError(INTERNAL_DETAIL)

    @app.get("/missing")
    def missing() -> None:
        raise NotFoundError("paper 1 not found")

    return app


def test_unexpected_errors_return_a_fixed_envelope_without_internal_details() -> None:
    client = TestClient(_app(), raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": INTERNAL_ERROR_MESSAGE}
    }
    for leaked in ("fake-pw-not-real", "postgresql", "/app/data", "Traceback", "RuntimeError"):
        assert leaked not in response.text


def test_expected_errors_keep_their_own_status_and_message() -> None:
    response = TestClient(_app()).get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_container_does_not_write_an_access_log_with_query_strings() -> None:
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "--no-access-log" in dockerfile
