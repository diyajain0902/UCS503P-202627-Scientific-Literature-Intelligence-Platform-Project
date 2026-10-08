"""Evaluation dataset and corpus manifest (FR-19, AC-19.1).

Relevance labels are quotes, not chunk IDs: a passage is relevant to an item if it comes from the
labelled paper and contains one of the item's evidence quotes (whitespace- and case-normalised).
This keeps labels valid when the chunker changes (M6 experiments) and makes every label checkable
against the source text.
"""

import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = REPO_ROOT / "eval"

_ARXIV_BASE = re.compile(r"^\d{4}\.\d{4,5}$")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase and collapse whitespace (PDF line breaks must not break quote matching)."""
    return _SPACE.sub(" ", text).strip().lower()


class CorpusPaper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arxiv_id: str = Field(pattern=_ARXIV_BASE.pattern)
    version: int = Field(ge=1)
    title: str = Field(min_length=1)


class CorpusManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    domain: str
    papers: list[CorpusPaper] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "CorpusManifest":
        ids = [p.arxiv_id for p in self.papers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate arxiv_id in corpus manifest")
        return self


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arxiv_id: str = Field(pattern=_ARXIV_BASE.pattern)
    quote: str = Field(min_length=12, max_length=300)
    """Verbatim text from the paper's extracted text (whitespace may differ)."""


class EvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^q\d{3}$")
    question: str = Field(min_length=8)
    kind: Literal["answerable", "unanswerable"]
    answer: str | None = Field(default=None, description="Short reference answer (answerable only)")
    evidence: list[Evidence] = Field(default_factory=list)
    labeler: str = Field(min_length=1)
    labeled_on: date
    review_status: Literal["unreviewed", "human_reviewed"]
    reviewer: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "EvalItem":
        if self.kind == "answerable" and (not self.evidence or not self.answer):
            raise ValueError(f"{self.id}: answerable items need evidence and an answer")
        if self.kind == "unanswerable" and (self.evidence or self.answer):
            raise ValueError(f"{self.id}: unanswerable items must not have evidence or an answer")
        if self.review_status == "human_reviewed" and not self.reviewer:
            raise ValueError(f"{self.id}: human_reviewed items must name the reviewer")
        return self


class EvalDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    corpus: str
    items: list[EvalItem]

    @model_validator(mode="after")
    def _unique_ids(self) -> "EvalDataset":
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate item id")
        return self

    @property
    def answerable(self) -> list[EvalItem]:
        return [i for i in self.items if i.kind == "answerable"]

    @property
    def unanswerable(self) -> list[EvalItem]:
        return [i for i in self.items if i.kind == "unanswerable"]


def load_manifest(path: Path) -> CorpusManifest:
    return CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_dataset(path: Path) -> EvalDataset:
    data = json.loads(path.read_text(encoding="utf-8"))
    return EvalDataset.model_validate(data)


def is_relevant(item: EvalItem, paper_arxiv_id: str | None, chunk_text: str) -> bool:
    if paper_arxiv_id is None:
        return False
    text = normalize(chunk_text)
    return any(e.arxiv_id == paper_arxiv_id and normalize(e.quote) in text for e in item.evidence)
