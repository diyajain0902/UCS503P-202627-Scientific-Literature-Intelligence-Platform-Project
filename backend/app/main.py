"""FastAPI application factory."""

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import corpus, health, qa, routes
from app.container import Container, build_container
from app.core.config import Settings, get_settings
from app.core.errors import AppError, register_error_handlers
from app.core.logging import RequestIdMiddleware, configure_logging
from app.services.jobs import fail_interrupted_jobs

logger = logging.getLogger(__name__)


def _warm_up_models(container: Container) -> None:
    try:
        container.embedder.warm_up()
    except Exception:
        logger.exception("embedding_model_warm_up_failed")
    if container.ollama is not None and container.settings.ollama_warm_up:
        try:
            container.ollama.warm_up()
        except AppError as exc:
            # Ollama being off is a normal state: search still works and Q&A reports it (NFR-16).
            logger.warning("generation_model_warm_up_failed", extra={"reason": exc.message})


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    """Build the app. Pass ``container`` to inject test doubles; otherwise services are built on
    startup.
    """
    settings = settings or (container.settings if container else get_settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        active = container or build_container(settings)
        app.state.container = active
        if owned:
            try:
                fail_interrupted_jobs(active.session_factory)
            except Exception:
                logger.exception("startup_job_recovery_failed")
            threading.Thread(target=_warm_up_models, args=(active,), daemon=True).start()
        try:
            yield
        finally:
            if owned:
                active.close()

    app = FastAPI(
        title="Scientific Literature Intelligence Platform",
        version=__version__,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        lifespan=lifespan,
    )
    if container is not None:
        app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RequestIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(routes.router, prefix="/api/v1")
    app.include_router(qa.router, prefix="/api/v1")
    app.include_router(corpus.router, prefix="/api/v1")
    return app


def _create_default_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    return create_app(settings)


app = _create_default_app()
