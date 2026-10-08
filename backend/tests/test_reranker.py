"""Unit tests for CrossEncoderReranker (FR-25)."""

import uuid
from unittest.mock import MagicMock, patch

from app.db.models import Chunk, Paper
from app.retrieval.rerank import CrossEncoderReranker
from app.retrieval.search import ChunkHit


def make_hit(text: str, score: float = 0.5) -> ChunkHit:
    paper = Paper(
        id=uuid.uuid4(),
        source="arxiv",
        arxiv_id="1706.03762",
        title="Attention Is All You Need",
        authors=["Vaswani"],
        categories=["cs.CL"],
    )
    chunk = Chunk(
        id=uuid.uuid4(),
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


def test_reranker_returns_empty_when_no_hits() -> None:
    reranker = CrossEncoderReranker()
    assert reranker.rerank("query", [], top_k=5) == []


def test_reranker_returns_single_hit_without_inference() -> None:
    hit = make_hit("Single passage")
    reranker = CrossEncoderReranker()
    res = reranker.rerank("query", [hit], top_k=5)
    assert len(res) == 1
    assert res[0].chunk.text == "Single passage"


@patch("app.retrieval.rerank.CrossEncoder")
def test_reranker_scores_and_resorts_hits(mock_ce_cls: MagicMock) -> None:
    mock_model = MagicMock()
    # Return higher score for candidate 2 than candidate 1
    mock_model.predict.return_value = [0.1, 0.9]
    mock_ce_cls.return_value = mock_model

    reranker = CrossEncoderReranker(model_name="mock-cross-encoder")
    hit1 = make_hit("Low relevance passage")
    hit2 = make_hit("High relevance passage")

    reranked = reranker.rerank("attention mechanism", [hit1, hit2], top_k=2)
    assert len(reranked) == 2
    assert reranked[0].chunk.text == "High relevance passage"
    assert reranked[0].score == 0.9
    assert reranked[1].chunk.text == "Low relevance passage"
    assert reranked[1].score == 0.1
