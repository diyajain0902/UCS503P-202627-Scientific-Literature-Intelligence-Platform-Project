"""Hybrid and dense semantic search service (FR-08, FR-24, FR-25)."""

import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import DependencyUnavailableError, InvalidInputError
from app.retrieval.embedding import Embedder
from app.retrieval.rerank import RerankerProtocol
from app.retrieval.search import (
    ChunkHit,
    installed_pgvector_version,
    pgvector_version_problem,
    search_bm25_chunks,
    search_chunks,
    search_hybrid_chunks,
)


@dataclass(frozen=True)
class SearchResult:
    hits: list[ChunkHit]
    embedding_model: str
    took_ms: float


class SearchService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        embedder: Embedder,
        max_top_k: int,
        search_mode: str = "hybrid_rerank",
        rrf_k: int = 60,
        candidate_multiplier: int = 4,
        reranker: RerankerProtocol | None = None,
        dense_weight: float = 1.0,
        sparse_weight: float = 1.0,
    ) -> None:
        self._sessions = session_factory
        self._embedder = embedder
        self._max_top_k = max_top_k
        self._search_mode = search_mode
        self._rrf_k = rrf_k
        self._candidate_multiplier = candidate_multiplier
        self._reranker = reranker
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._pgvector_checked = False

    @property
    def embedding_model(self) -> str:
        return self._embedder.model_name

    @property
    def search_mode(self) -> str:
        return self._search_mode

    def describe(self, search_mode: str | None = None) -> dict[str, Any]:
        """Retrieval configuration recorded with answers, analyses, and evaluation runs (NFR-09)."""
        mode = search_mode or self._search_mode
        config: dict[str, Any] = {"search_mode": mode, "embedding_model": self.embedding_model}
        if mode in {"hybrid", "hybrid_rerank"}:
            config.update(
                rrf_k=self._rrf_k,
                candidate_multiplier=self._candidate_multiplier,
                dense_weight=self._dense_weight,
                sparse_weight=self._sparse_weight,
            )
        if mode == "hybrid_rerank":
            config["reranker_model"] = self._reranker.model_name if self._reranker else None
        return config

    def search(
        self,
        query: str,
        top_k: int,
        paper_ids: list[uuid.UUID] | None = None,
        search_mode: str | None = None,
    ) -> SearchResult:
        cleaned = " ".join(query.split())
        if not cleaned:
            raise InvalidInputError("query must contain text")
        if not 1 <= top_k <= self._max_top_k:
            raise InvalidInputError(f"top_k must be between 1 and {self._max_top_k}")

        mode = search_mode or self._search_mode
        if mode not in {"dense", "bm25", "hybrid", "hybrid_rerank"}:
            raise InvalidInputError(
                f"invalid search_mode '{mode}'; expected 'dense', 'bm25', 'hybrid', or "
                "'hybrid_rerank'"
            )

        started = time.perf_counter()

        with self._sessions() as session:
            self._require_supported_pgvector(session)

            vector = self._embedder.embed([cleaned])[0]
            if mode == "dense":
                hits = search_chunks(session, vector, top_k, paper_ids)
            elif mode == "bm25":
                hits = search_bm25_chunks(session, cleaned, vector, top_k, paper_ids)
            else:
                candidate_k = max(top_k * self._candidate_multiplier, 20)
                fused = search_hybrid_chunks(
                    session=session,
                    query_vector=vector,
                    query_text=cleaned,
                    top_k=candidate_k if mode == "hybrid_rerank" else top_k,
                    paper_ids=paper_ids,
                    candidate_k=candidate_k,
                    rrf_k=self._rrf_k,
                    dense_weight=self._dense_weight,
                    sparse_weight=self._sparse_weight,
                )
                hits = fused[:top_k]

        if mode == "hybrid_rerank" and self._reranker is not None:
            # Runs after the session is released: inference does not need a DB connection.
            hits = self._reranker.rerank(cleaned, fused, top_k)

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
