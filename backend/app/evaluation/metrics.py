"""Retrieval and answer metrics (FR-19, FR-20). Pure functions; definitions in docs/evaluation.md.

Recall@k follows the proposal: the fraction of queries with at least one relevant passage in the top
k (sometimes called hit rate). MRR uses the rank of the first relevant passage, 0 if none in the
ranking.
"""

import math
from collections.abc import Sequence


def recall_at_k(rankings: Sequence[Sequence[bool]], k: int) -> float:
    """``rankings[q][i]`` is True when the passage at rank i+1 for query q is relevant."""
    if k < 1:
        raise ValueError("k must be >= 1")
    if not rankings:
        raise ValueError("no queries")
    return sum(1 for ranks in rankings if any(ranks[:k])) / len(rankings)


def reciprocal_rank(ranks: Sequence[bool]) -> float:
    for position, relevant in enumerate(ranks, start=1):
        if relevant:
            return 1.0 / position
    return 0.0


def mean_reciprocal_rank(rankings: Sequence[Sequence[bool]]) -> float:
    if not rankings:
        raise ValueError("no queries")
    return sum(reciprocal_rank(r) for r in rankings) / len(rankings)


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile (no interpolation), p in (0, 100]."""
    if not values:
        raise ValueError("no values")
    if not 0 < p <= 100:
        raise ValueError("p must be in (0, 100]")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def ratio(numerator: int, denominator: int) -> float | None:
    """A rate, or None when undefined (reported as such rather than as 0 or 1)."""
    return numerator / denominator if denominator else None
