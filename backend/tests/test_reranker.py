"""Unit tests for CrossEncoderReranker (FR-25)."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import DependencyUnavailableError
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

    hit1 = make_hit("Low relevance passage", score=0.62)
    hit2 = make_hit("High relevance passage", score=0.41)

    reranked = reranker.rerank("attention mechanism", [hit1, hit2], top_k=2)
    assert len(reranked) == 2
    assert reranked[0].chunk.text == "High relevance passage"
    assert reranked[0].rank_score == 0.9
    assert reranked[1].chunk.text == "Low relevance passage"
    assert reranked[1].rank_score == 0.1


@patch("app.retrieval.rerank.CrossEncoder")
def test_reranker_keeps_cosine_score_for_evidence_thresholds(mock_ce_cls: MagicMock) -> None:
    # Regression (M6): cross-encoder logits replaced ChunkHit.score, so qa_min_score (calibrated on
    # cosine similarity) was compared with logits. Logits such as -7.5 must not touch the score.
    mock_model = MagicMock()
    mock_model.predict.return_value = [-7.5, 4.2]
    mock_ce_cls.return_value = mock_model
    hits = [make_hit("a", score=0.55), make_hit("b", score=0.33)]

    reranked = CrossEncoderReranker(model_name="mock").rerank("q", hits, top_k=2)

    assert [h.score for h in reranked] == [0.33, 0.55]
    assert [h.rank_score for h in reranked] == [4.2, -7.5]


@patch("app.retrieval.rerank.CrossEncoder", side_effect=OSError("offline"))
def test_reranker_load_failure_is_a_dependency_error(_: MagicMock) -> None:
    reranker = CrossEncoderReranker(model_name="missing")
    with pytest.raises(DependencyUnavailableError, match="could not be loaded"):
        reranker.rerank("q", [make_hit("a"), make_hit("b")], top_k=2)
