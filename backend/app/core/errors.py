"""Domain errors and their HTTP mapping.

Every error response uses the envelope ``{"error": {"code": str, "message": str}}``.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "An internal error occurred. Details were written to the server log."
DATABASE_UNAVAILABLE_MESSAGE = (
    "The database is unavailable. Check that PostgreSQL is running (GET /api/v1/ready shows "
    "each dependency)."
)


class AppError(Exception):
    """Base class for expected, user-reportable errors."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    """The request conflicts with existing state (e.g. a duplicate upload)."""

    status_code = 409
    code = "conflict"


class InvalidInputError(AppError):
    status_code = 422
    code = "invalid_input"


class UpstreamError(AppError):
    """An external dependency (arXiv, Ollama) failed or returned unusable data."""

    status_code = 502
    code = "upstream_error"


class DocumentRejectedError(AppError):
    """A PDF cannot be processed (too large, encrypted, scanned, corrupt)."""

    status_code = 422
    code = "document_rejected"


class DependencyUnavailableError(AppError):
    status_code = 503
    code = "dependency_unavailable"


class GenerationTimeoutError(AppError):
    """The local model did not answer within the configured timeout."""

    status_code = 504
    code = "generation_timeout"


class MalformedModelOutputError(AppError):
    """The local model returned output that does not match the required schema (AC-09.3)."""

    status_code = 502
    code = "malformed_model_output"


def _envelope(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _envelope(exc.code, exc.message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        message = (
            f"{location}: {first.get('msg', 'invalid request')}" if location else "invalid request"
        )
        return _envelope("invalid_input", message, 422)

    @app.exception_handler(OperationalError)
    async def _database_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
        # Connection-level failures (server down, refused, dropped); details stay in the log.
        logger.error("database_unavailable", exc_info=exc)
        return _envelope("dependency_unavailable", DATABASE_UNAVAILABLE_MESSAGE, 503)

    @app.exception_handler(Exception)
    async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        # Details (type, message, traceback) go to the server log only; the client gets a fixed
        # message so file paths, SQL, or configuration never leak (security audit, step 5b).
        logger.error("unhandled_error", exc_info=exc)
        return _envelope("internal_error", INTERNAL_ERROR_MESSAGE, 500)
