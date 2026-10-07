"""Tests against the real all-MiniLM-L6-v2 model (marker ``model``; downloads ~90 MB once)."""

import math

import pytest

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.pdf import ExtractedDocument
from app.retrieval.embedding import SentenceTransformerEmbedder

pytestmark = pytest.mark.model


@pytest.fixture(scope="module")
def embedder() -> SentenceTransformerEmbedder:
    model = SentenceTransformerEmbedder(
        "sentence-transformers/all-MiniLM-L6-v2", 384, "cpu", 32, min_input_tokens=256
    )
    model.warm_up()
    return model


def test_model_limits_match_adr_0003(embedder: SentenceTransformerEmbedder) -> None:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    assert model.max_seq_length == 256
    assert model.get_embedding_dimension() == 384


def test_vectors_are_384_dim_and_normalized(embedder: SentenceTransformerEmbedder) -> None:
    vectors = embedder.embed(["attention mechanisms", "graph neural networks"])
    assert [len(v) for v in vectors] == [384, 384]
    assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-4) for v in vectors)


def test_semantic_similarity_sanity(embedder: SentenceTransformerEmbedder) -> None:
    query, related, unrelated = embedder.embed(
        [
            "neural machine translation",
            "Sequence-to-sequence models translate sentences between languages.",
            "Preheat the oven and knead the bread dough.",
        ]
    )

    def dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert dot(query, related) > dot(query, unrelated)


def test_real_tokenizer_chunks_fit_model_input(embedder: SentenceTransformerEmbedder) -> None:
    text = " ".join(
        f"Sentence {i} discusses BERT-style pre-training, état-of-the-art résumés, and F1=0.{i}."
        for i in range(400)
    )
    document = ExtractedDocument(text=text, page_starts=(0,))
    tokenizer = embedder.tokenizer()
    chunks = chunk_document(document, "c" * 64, tokenizer, ChunkingConfig(256, 38))
    assert len(chunks) > 5
    for chunk in chunks:
        assert chunk.token_count <= 254
        # Re-tokenizing the stored chunk text must not exceed the model's content window.
        assert len(tokenizer.token_spans(chunk.text)) <= 254
        assert text[chunk.char_start : chunk.char_end] == chunk.text
