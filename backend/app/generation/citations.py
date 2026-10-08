"""Deterministic citation validation (FR-10, AC-10.1-AC-10.4).

This checks that cited labels refer to passages the model was actually given. It does NOT check that
a passage semantically supports the claim; that is measured separately (groundedness evaluation,
FR-20).
"""

import re
from dataclasses import dataclass
from typing import Literal

from app.generation.prompts import ModelAnswer

Support = Literal["cited", "unsupported"]
"""``cited``: at least one valid citation (semantic support not verified). ``unsupported``: none."""


@dataclass(frozen=True)
class CheckedCitation:
    label: str
    valid: bool


@dataclass(frozen=True)
class CheckedClaim:
    text: str
    support: Support
    citations: list[CheckedCitation]


@dataclass(frozen=True)
class CheckedAnswer:
    model_status: Literal["answered", "insufficient_evidence"]
    claims: list[CheckedClaim]
    dropped_claims: int = 0
    """Claims discarded because their text had no content beyond citation labels."""

    @property
    def has_supported_claim(self) -> bool:
        return any(claim.support == "cited" for claim in self.claims)

    @property
    def invalid_citation_count(self) -> int:
        return sum(1 for c in self.claims for cit in c.citations if not cit.valid)


_LABEL_TOKEN = re.compile(r"\[?\bP\d+\b\]?", re.IGNORECASE)


def has_substance(text: str) -> bool:
    """False for "claims" that are only citation labels and punctuation (e.g. "P1", "[P2] P3")."""
    remainder = _LABEL_TOKEN.sub("", text)
    return sum(ch.isalnum() for ch in remainder) >= 2


def _normalize_label(raw: str) -> str:
    return raw.strip().strip("[]").strip().upper()


def check_citations(answer: ModelAnswer, supplied_labels: set[str]) -> CheckedAnswer:
    claims: list[CheckedClaim] = []
    dropped = 0
    for claim in answer.claims:
        if not has_substance(claim.text):
            dropped += 1
            continue
        seen: set[str] = set()
        citations: list[CheckedCitation] = []
        for raw in claim.citations:
            label = _normalize_label(raw)
            if not label or label in seen:
                continue
            seen.add(label)
            citations.append(CheckedCitation(label=label, valid=label in supplied_labels))
        support: Support = "cited" if any(c.valid for c in citations) else "unsupported"
        claims.append(CheckedClaim(text=claim.text.strip(), support=support, citations=citations))
    return CheckedAnswer(model_status=answer.status, claims=claims, dropped_claims=dropped)
