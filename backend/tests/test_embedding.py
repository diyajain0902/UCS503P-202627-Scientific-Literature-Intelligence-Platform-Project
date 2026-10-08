import sys
import types
from typing import Any

import pytest

from app.core.errors import DependencyUnavailableError
from app.retrieval.embedding import (
    EmbeddingDimensionError,
    HuggingFaceTokenizer,
    SentenceTransformerEmbedder,
    check_vectors,
)


class _FakeModel:
    """Stands in for sentence_transformers.SentenceTransformer (no download)."""

    dimension = 384
    max_seq_length: int | None = 256

    def __init__(self, name: str, device: str) -> None:
        self.tokenizer = None

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]


@pytest.fixture
def fake_st(monkeypatch: pytest.MonkeyPatch) -> type[_FakeModel]:
    model = type("Model", (_FakeModel,), {})
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return model


def _embedder(min_tokens: int = 256) -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder("fake/model", 384, "cpu", 8, min_tokens)


def test_check_vectors() -> None:
    check_vectors([[0.0] * 3], 1, 3)
    with pytest.raises(EmbeddingDimensionError):
        check_vectors([[0.0] * 2], 1, 3)
    with pytest.raises(EmbeddingDimensionError):
        check_vectors([], 1, 3)


def test_embedder_validates_output_dimension(fake_st: type[_FakeModel]) -> None:
    embedder = _embedder()
    assert len(embedder.embed(["a", "b"])[1]) == 384
    assert embedder.is_loaded
    assert embedder.embed([]) == []


def test_embedder_rejects_wrong_model_dimension(fake_st: type[_FakeModel]) -> None:
    fake_st.dimension = 768
    embedder = _embedder()
    with pytest.raises(DependencyUnavailableError):
        embedder.warm_up()
    assert embedder.load_error is not None and "768" in embedder.load_error
    assert not embedder.is_loaded


def test_embedder_rejects_model_shorter_than_chunk_window(fake_st: type[_FakeModel]) -> None:
    fake_st.max_seq_length = 128
    embedder = _embedder(min_tokens=256)
    with pytest.raises(DependencyUnavailableError, match="ADR-0003"):
        embedder.warm_up()


def test_hf_tokenizer_adapter_drops_empty_spans() -> None:
    def fake_tokenizer(text: str, **kwargs: Any) -> dict[str, list[tuple[int, int]]]:
        assert kwargs["add_special_tokens"] is False
        return {"offset_mapping": [(0, 3), (3, 3), (4, 7)]}

    adapter = HuggingFaceTokenizer(fake_tokenizer, "fake")
    assert adapter.token_spans("abc def") == [(0, 3), (4, 7)]
