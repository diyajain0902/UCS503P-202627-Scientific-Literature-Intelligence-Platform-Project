"""Cross-encoder reranking for candidate retrieval passages (FR-25)."""

from typing import Protocol

from sentence_transformers import CrossEncoder

from app.retrieval.search import ChunkHit


class RerankerProtocol(Protocol):
    def rerank(self, query: str, hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
        """Rerank candidates using a cross-encoder model and return top_k."""
        ...


class CrossEncoderReranker:
    """Cross-encoder reranker wrapping sentence-transformers CrossEncoder."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model: CrossEncoder | None = None

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def rerank(self, query: str, hits: list[ChunkHit], top_k: int) -> list[ChunkHit]:
        if not hits:
            return []
        if len(hits) == 1:
            return hits[:top_k]

        model = self._get_model()
        pairs = [(query, hit.chunk.text) for hit in hits]
        # Compute cross-encoder logit scores
        scores = model.predict(pairs)
        if isinstance(scores, float):
            scores = [scores]

        scored_hits = [
            ChunkHit(
                chunk=hit.chunk,
                paper=hit.paper,
                score=float(score),
            )
            for hit, score in zip(hits, scores, strict=True)
        ]
        # Sort descending by cross-encoder score
        scored_hits.sort(key=lambda h: h.score, reverse=True)
        return scored_hits[:top_k]


type Reranker = CrossEncoderReranker
