"""Unit tests for SearchService search_mode routing and RRF rank fusion logic (FR-24, FR-25)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import InvalidInputError
from app.db.models import Chunk, Paper
from app.retrieval.search import ChunkHit, bm25_terms, search_hybrid_chunks
from app.services.search import SearchService


def make_hit(text: str, cid: uuid.UUID | None = None, score: float = 0.5) -> ChunkHit:
    paper = Paper(
        id=uuid.uuid4(),
        source="arxiv",
        arxiv_id="1706.03762",
        title="Test Paper",
        authors=["Author"],
        categories=["cs.CL"],
    )
    chunk = Chunk(
        id=cid or uuid.uuid4(),
        ordinal=0,
        page_start=1,
        page_end=1,
        char_start=0,
        char_end=len(text),
        token_count=10,
        text=text,
        embedding=[0.0] * 384,
    )
    return ChunkHit(chunk=chunk, paper=paper, score=score)


def test_search_service_invalid_mode_raises_error() -> None:
    session_factory = MagicMock()
    embedder = MagicMock()
    embedder.model_name = "test-model"
    service = SearchService(session_factory, embedder, max_top_k=50)

    with pytest.raises(InvalidInputError, match="invalid search_mode"):
        service.search("transformer", top_k=5, search_mode="invalid_mode")


def test_rrf_rank_fusion_combines_dense_and_sparse_hits() -> None:
    cid1 = uuid.uuid4()
    cid2 = uuid.uuid4()
    cid3 = uuid.uuid4()

    hit1 = make_hit("Chunk 1", cid=cid1)
    hit2 = make_hit("Chunk 2", cid=cid2)
    hit3 = make_hit("Chunk 3", cid=cid3)

    session = MagicMock()

    # Mock dense hits: hit1 (rank 1), hit2 (rank 2)
    # Mock BM25 hits: hit3 (rank 1), hit1 (rank 2)
    with (
        MagicMock() as mock_dense,
        MagicMock() as mock_bm25,
    ):
        mock_dense.return_value = [hit1, hit2]
        mock_bm25.return_value = [hit3, hit1]

        with (
            patch("app.retrieval.search.search_chunks", return_value=[hit1, hit2]),
            patch("app.retrieval.search.search_bm25_chunks", return_value=[hit3, hit1]),
        ):
            fused = search_hybrid_chunks(
                session=session,
                query_vector=[0.1] * 384,
                query_text="transformer model",
                top_k=3,
                candidate_k=10,
                rrf_k=60,
            )

    # Chunk 1 appears in both lists (dense rank 1, sparse rank 2), so its RRF score is highest:
    # 1/(60+1) + 1/(60+2) = 0.01639 + 0.01612 = 0.03251
    assert len(fused) == 3
    assert fused[0].chunk.id == cid1


def test_rrf_keeps_cosine_score_and_records_fusion_score() -> None:
    dense = make_hit("dense", score=0.71)
    sparse = make_hit("sparse", score=0.12)
    with (
        patch("app.retrieval.search.search_chunks", return_value=[dense]),
        patch("app.retrieval.search.search_bm25_chunks", return_value=[sparse]),
    ):
        fused = search_hybrid_chunks(MagicMock(), [0.1] * 384, "q", top_k=2, rrf_k=60)

    by_text = {h.chunk.text: h for h in fused}
    assert by_text["dense"].score == 0.71
    assert by_text["sparse"].score == 0.12
    assert by_text["dense"].rank_score == pytest.approx(1 / 61)
    assert by_text["sparse"].rank_score == pytest.approx(1 / 61)


def test_rrf_ties_are_broken_by_chunk_id() -> None:
    low, high = sorted([uuid.uuid4(), uuid.uuid4()], key=str)
    a, b = make_hit("a", cid=high), make_hit("b", cid=low)
    with (
        patch("app.retrieval.search.search_chunks", return_value=[a]),
        patch("app.retrieval.search.search_bm25_chunks", return_value=[b]),
    ):
        fused = search_hybrid_chunks(MagicMock(), [0.1] * 384, "q", top_k=2)
    assert [h.chunk.id for h in fused] == [low, high]


def test_bm25_terms_strip_tsquery_syntax() -> None:
    assert bm25_terms("BERT's (masked) LM & a | b:* !x") == ["BERTs", "masked", "LM"]


def test_describe_records_retrieval_configuration() -> None:
    embedder = MagicMock()
    embedder.model_name = "emb"
    reranker = MagicMock()
    reranker.model_name = "ce"
    service = SearchService(MagicMock(), embedder, 50, rrf_k=30, reranker=reranker)

    assert service.describe("dense") == {"search_mode": "dense", "embedding_model": "emb"}
    assert service.describe() == {
        "search_mode": "hybrid_rerank",
        "embedding_model": "emb",
        "rrf_k": 30,
        "candidate_multiplier": 4,
        "dense_weight": 1.0,
        "sparse_weight": 1.0,
        "reranker_model": "ce",
    }
