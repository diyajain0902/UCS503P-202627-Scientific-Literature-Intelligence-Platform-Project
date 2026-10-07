"""Readiness checks for each dependency, reported individually (IR-05)."""

from dataclasses import dataclass

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.retrieval.embedding import ManagedEmbedder


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str


def check_database(session_factory: sessionmaker[Session]) -> CheckResult:
    try:
        with session_factory() as session:
            version = session.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one_or_none()
            revision = session.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    except Exception as exc:
        return CheckResult(False, f"unreachable or not migrated ({type(exc).__name__})")
    if version is None:
        return CheckResult(False, "pgvector extension not installed")
    return CheckResult(True, f"pgvector {version}, schema revision {revision}")


def check_embedder(embedder: ManagedEmbedder) -> CheckResult:
    if embedder.is_loaded:
        return CheckResult(True, f"{embedder.model_name} loaded ({embedder.dimension}-dim)")
    if embedder.load_error:
        return CheckResult(False, embedder.load_error)
    return CheckResult(False, "loading")


def check_ollama(base_url: str, model: str, timeout_seconds: float = 2.0) -> CheckResult:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        names = {entry.get("name") for entry in response.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as exc:
        return CheckResult(False, f"unreachable ({type(exc).__name__})")
    if model not in names:
        return CheckResult(False, f"model '{model}' not installed")
    return CheckResult(True, f"model '{model}' available")
