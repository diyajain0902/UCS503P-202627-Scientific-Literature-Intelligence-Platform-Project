"""Liveness and readiness endpoints (IR-05)."""

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from app import __version__
from app.api.v1.schemas import CheckOut, ReadinessResponse
from app.container import Container
from app.services.health import check_database, check_embedder, check_ollama, check_reranker

router = APIRouter(tags=["health"])

# Search depends on these (the reranker only in hybrid_rerank mode); Ollama is reported but only
# Q&A depends on it (NFR-16).
_REQUIRED_FOR_READY = ("database", "embedding_model", "reranker")


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is running. Use ``/ready`` for dependency status."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request, response: Response) -> ReadinessResponse:
    container: Container = request.app.state.container
    settings = container.settings
    checks = {
        "database": check_database(container.session_factory),
        "embedding_model": check_embedder(container.embedder),
        "reranker": check_reranker(container.reranker, settings.search_mode),
        "ollama": check_ollama(str(settings.ollama_base_url), settings.ollama_model),
    }
    is_ready = all(checks[name].ok for name in _REQUIRED_FOR_READY)
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        checks={name: CheckOut(ok=c.ok, detail=c.detail) for name, c in checks.items()},
    )
