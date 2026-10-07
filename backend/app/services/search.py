"""Semantic search use case (FR-08)."""

import time
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import InvalidInputError
from app.retrieval.embedding import Embedder
from app.retrieval.search import ChunkHit, search_chunks


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
            # Closing the session ends the read-only transaction (and its SET LOCAL settings)
            # without expiring the loaded rows, which a rollback() would do.
            hits = search_chunks(session, vector, top_k, paper_ids)
        return SearchResult(
            hits=hits,
            embedding_model=self._embedder.model_name,
            took_ms=round((time.perf_counter() - started) * 1000, 1),
        )
