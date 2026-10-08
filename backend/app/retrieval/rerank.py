"""Cross-encoder reranking for candidate retrieval passages (FR-25)."""

import threading
from dataclasses import replace
from typing import Protocol

from sentence_transformers import CrossEncoder

from app.core.errors import DependencyUnavailableError
from app.retrieval.search import ChunkHit


class RerankerProtocol(Protocol):
    @property
    def model_name(self) -> str: ...

    def rerank(self, query: str, hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
        """Order candidates by cross-encoder relevance and return the best ``top_k``."""
        ...


class CrossEncoderReranker:
    """Cross-encoder reranker wrapping sentence-transformers ``CrossEncoder``.

    The cross-encoder logit is stored in ``ChunkHit.rank_score``; ``ChunkHit.score`` keeps the
    cosine similarity, because evidence thresholds are calibrated on it (not on logits).
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self.device = device
        self._model: CrossEncoder | None = None
        self._lock = threading.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def warm_up(self) -> None:
        self._get_model()

    def _get_model(self) -> CrossEncoder:
        with self._lock:
            if self._model is None:
                try:
                    self._model = CrossEncoder(self._model_name, device=self.device)
                except (OSError, ValueError) as exc:
                    raise DependencyUnavailableError(
                        f"Reranker model '{self._model_name}' could not be loaded"
                    ) from exc
            return self._model

    def rerank(self, query: str, hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
        if len(hits) <= 1:
            return hits[:top_k]

        model = self._get_model()
        scores = model.predict([(query, hit.chunk.text) for hit in hits])
        scored = [
            replace(hit, rank_score=float(score)) for hit, score in zip(hits, scores, strict=True)
        ]
        # Stable sort: equal logits keep their fused (RRF) order.
        scored.sort(key=lambda h: h.rank_score or 0.0, reverse=True)
        return scored[:top_k]
