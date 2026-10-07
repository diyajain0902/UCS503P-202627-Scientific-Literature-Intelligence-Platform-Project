"""Local sentence-transformers embeddings (FR-06).

The model is loaded once (lazily, thread-safe). Vectors are L2-normalized and their dimension is
validated against the configured/schema dimension on every call (AC-06.1, AC-06.3).
"""

import logging
import threading
import time
from typing import TYPE_CHECKING, Protocol

from app.core.errors import DependencyUnavailableError
from app.ingestion.chunking import SPECIAL_TOKENS_PER_INPUT, Tokenizer

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    model_name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ManagedEmbedder(Embedder, Protocol):
    """An embedder with a load lifecycle and access to its tokenizer (used by readiness and
    chunking).
    """

    @property
    def is_loaded(self) -> bool: ...

    @property
    def load_error(self) -> str | None: ...

    def warm_up(self) -> None: ...

    def tokenizer(self) -> "Tokenizer": ...


class EmbeddingDimensionError(RuntimeError):
    pass


def check_vectors(vectors: list[list[float]], expected_count: int, dimension: int) -> None:
    if len(vectors) != expected_count:
        raise EmbeddingDimensionError(f"expected {expected_count} vectors, got {len(vectors)}")
    for vector in vectors:
        if len(vector) != dimension:
            raise EmbeddingDimensionError(f"expected dimension {dimension}, got {len(vector)}")


class HuggingFaceTokenizer:
    """Adapter exposing the embedding model's own WordPiece tokenizer to the chunker."""

    def __init__(self, hf_tokenizer: object, name: str) -> None:
        self._tokenizer = hf_tokenizer
        self.name = name

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        encoding = self._tokenizer(  # type: ignore[operator]
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
            verbose=False,
        )
        return [(int(start), int(end)) for start, end in encoding["offset_mapping"] if end > start]


class SentenceTransformerEmbedder:
    def __init__(
        self,
        model_name: str,
        dimension: int,
        device: str,
        batch_size: int,
        min_input_tokens: int,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self._device = device
        self._batch_size = batch_size
        self._min_input_tokens = min_input_tokens
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()
        self.load_error: str | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> "SentenceTransformer":
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            from sentence_transformers import SentenceTransformer

            started = time.perf_counter()
            try:
                model = SentenceTransformer(self.model_name, device=self._device)
            except Exception as exc:
                self.load_error = f"{type(exc).__name__}: {exc}"[:300]
                raise DependencyUnavailableError(
                    f"Embedding model '{self.model_name}' could not be loaded"
                ) from exc
            actual_dim = model.get_embedding_dimension()
            if actual_dim != self.dimension:
                self.load_error = f"model dimension {actual_dim} != configured {self.dimension}"
                raise DependencyUnavailableError(self.load_error)
            max_seq_length = model.max_seq_length or 0
            if max_seq_length < self._min_input_tokens:
                self.load_error = (
                    f"model max_seq_length {max_seq_length} < chunk window "
                    f"{self._min_input_tokens} (ADR-0003)"
                )
                raise DependencyUnavailableError(self.load_error)
            self.load_error = None
            self._model = model
            logger.info(
                "embedding_model_loaded",
                extra={
                    "model": self.model_name,
                    "dimension": actual_dim,
                    "max_seq_length": model.max_seq_length,
                    "seconds": round(time.perf_counter() - started, 2),
                },
            )
            return model

    def warm_up(self) -> None:
        self._load()

    def tokenizer(self) -> HuggingFaceTokenizer:
        return HuggingFaceTokenizer(self._load().tokenizer, name=self.model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        matrix = model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = [[float(x) for x in row] for row in matrix]
        check_vectors(vectors, len(texts), self.dimension)
        return vectors


def required_input_tokens(window_tokens: int) -> int:
    """Input length (including special tokens) the embedder must accept for a given chunk window."""
    return max(window_tokens, SPECIAL_TOKENS_PER_INPUT + 1)
