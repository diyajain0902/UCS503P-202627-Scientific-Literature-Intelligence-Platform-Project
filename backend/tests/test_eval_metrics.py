"""Metric implementations checked against hand-computed values (AC-19.2)."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.evaluation.dataset import EvalItem, Evidence, is_relevant, normalize
from app.evaluation.metrics import (
    mean_reciprocal_rank,
    percentile,
    ratio,
    recall_at_k,
    reciprocal_rank,
)

T, F = True, False

# Four queries. First relevant ranks: 1, 3, none, 2.
RANKINGS = [
    [T, F, F, F, F],
    [F, F, T, F, F],
    [F, F, F, F, F],
    [F, T, T, F, F],
]


def test_recall_at_k_hand_computed() -> None:
    assert recall_at_k(RANKINGS, 1) == 1 / 4
    assert recall_at_k(RANKINGS, 2) == 2 / 4
    assert recall_at_k(RANKINGS, 3) == 3 / 4
    assert recall_at_k(RANKINGS, 5) == 3 / 4


def test_mrr_hand_computed() -> None:
    # (1/1 + 1/3 + 0 + 1/2) / 4 = 0.4583...
    assert mean_reciprocal_rank(RANKINGS) == pytest.approx((1 + 1 / 3 + 0 + 0.5) / 4)
    assert reciprocal_rank([F, F, F]) == 0.0


def test_metric_inputs_validated() -> None:
    with pytest.raises(ValueError):
        recall_at_k(RANKINGS, 0)
    with pytest.raises(ValueError):
        recall_at_k([], 5)
    with pytest.raises(ValueError):
        mean_reciprocal_rank([])


def test_percentile_nearest_rank() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert percentile(values, 50) == 50.0
    assert percentile(values, 95) == 100.0
    assert percentile(values, 90) == 90.0
    assert percentile([5.0], 95) == 5.0


def test_ratio_is_none_when_undefined() -> None:
    assert ratio(3, 4) == 0.75
    assert ratio(0, 0) is None


def _item(**overrides: object) -> EvalItem:
    values: dict[str, object] = {
        "id": "q001",
        "question": "How many heads are used?",
        "kind": "answerable",
        "answer": "Eight",
        "evidence": [
            {"arxiv_id": "1706.03762", "quote": "we employ h = 8 parallel attention layers"}
        ],
        "labeler": "ai-assistant",
        "labeled_on": date(2026, 10, 8),
        "review_status": "unreviewed",
    }
    values.update(overrides)
    return EvalItem.model_validate(values)


def test_relevance_matches_quote_across_line_breaks_and_case() -> None:
    item = _item()
    chunk = "In this work we employ h = 8 parallel\nattention layers, or heads."
    assert is_relevant(item, "1706.03762", chunk)
    assert is_relevant(item, "1706.03762", chunk.upper())
    assert not is_relevant(item, "1810.04805", chunk)  # right text, wrong paper
    assert not is_relevant(item, None, chunk)
    assert not is_relevant(item, "1706.03762", "we employ h = 8 parallel")  # partial quote
    assert normalize("  A\n\tB  ") == "a b"


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "answerable", "evidence": []},
        {"kind": "answerable", "answer": None},
        {"kind": "unanswerable"},  # still has evidence and answer
        {"review_status": "human_reviewed"},  # no reviewer named
        {"id": "Q1"},
    ],
)
def test_inconsistent_items_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _item(**overrides)


def test_valid_unanswerable_item() -> None:
    item = _item(kind="unanswerable", answer=None, evidence=[])
    assert item.kind == "unanswerable"
    assert Evidence(arxiv_id="1706.03762", quote="twelve characters").quote
