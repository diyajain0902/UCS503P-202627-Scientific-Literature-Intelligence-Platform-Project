"""Regression: pgvector < 0.8.0 rejects ``hnsw.iterative_scan`` ("reserved prefix").

Before the version guard this turned every search into an unexplained HTTP 500. Found 2026-10-08
against a local pgvector 0.6.2.
"""

import pytest

from app.retrieval.search import parse_version, pgvector_version_problem


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [("0.8.0", (0, 8, 0)), ("0.10.1", (0, 10, 1)), ("0.6.2", (0, 6, 2)), ("0.8.0-dev", (0, 8, 0))],
)
def test_parse_version(raw: str, parsed: tuple[int, ...]) -> None:
    assert parse_version(raw) == parsed


@pytest.mark.parametrize("version", ["0.8.0", "0.8.1", "0.10.0", "1.0.0"])
def test_supported_versions(version: str) -> None:
    assert pgvector_version_problem(version) is None


def test_old_version_reported_clearly() -> None:
    assert pgvector_version_problem("0.6.2") == (
        "pgvector 0.6.2 is installed; 0.8.0 or newer is required"
    )


def test_missing_extension_reported() -> None:
    assert pgvector_version_problem(None) == "pgvector extension not installed"
