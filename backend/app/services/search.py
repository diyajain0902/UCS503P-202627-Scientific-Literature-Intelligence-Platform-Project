"""Semantic search use case (FR-08)."""

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DependencyUnavailableError, InvalidInputError
from app.retrieval.embedding import Embedder
from app.retrieval.search import (
    ChunkHit,
    installed_pgvector_version,
    pgvector_version_problem,
    search_chunks,
)


@dataclass(frozen=True)
class SearchResult:
    hits: list[ChunkHit]
    embedding_model: str
    took_ms: float


class SearchService:
    def __init__(
        self, session_factory: sessionmaker[Session], embedder: Embedder, max_top_k: int
    ) -> None:
        self._sessions = session_factory
        self._embedder = embedder
        self._max_top_k = max_top_k
        self._pgvector_checked = False

    @property
    def embedding_model(self) -> str:
        return self._embedder.model_name

    def search(
        self, query: str, top_k: int, paper_ids: list[uuid.UUID] | None = None
    ) -> SearchResult:
        cleaned = " ".join(query.split())
        if not cleaned:
            raise InvalidInputError("query must contain text")
        if not 1 <= top_k <= self._max_top_k:
            raise InvalidInputError(f"top_k must be between 1 and {self._max_top_k}")
        started = time.perf_counter()
        vector = self._embedder.embed([cleaned])[0]
        with self._sessions() as session:
            self._require_supported_pgvector(session)
            # Closing the session ends the read-only transaction (and its SET LOCAL settings)
            # without expiring the loaded rows, which a rollback() would do.
            hits = search_chunks(session, vector, top_k, paper_ids)
        return SearchResult(
            hits=hits,
            embedding_model=self._embedder.model_name,
            took_ms=round((time.perf_counter() - started) * 1000, 1),
        )

    def _require_supported_pgvector(self, session: Session) -> None:
        """Fail with a clear 503 instead of a database error on an unsupported pgvector version."""
        if self._pgvector_checked:
            return
        problem = pgvector_version_problem(installed_pgvector_version(session))
        if problem is not None:
            raise DependencyUnavailableError(f"Search unavailable: {problem}")
        self._pgvector_checked = True
