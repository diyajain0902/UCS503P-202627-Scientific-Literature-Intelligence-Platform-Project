"""Controlled test doubles. Everything here is synthetic; never present it as real data."""

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from sqlalchemy.orm import Session, sessionmaker

from app.container import Container, qa_limits
from app.core.config import Settings
from app.generation.provider import GenerationRequest, GenerationResult
from app.ingestion.arxiv import ArxivId, ArxivMetadata
from app.ingestion.chunking import ChunkingConfig, Tokenizer
from app.ingestion.storage import FileStore
from app.services.corpus import CorpusService
from app.services.ingestion import IngestionService
from app.services.jobs import JobRunner
from app.services.qa import QAService
from app.services.search import SearchService

DIMENSION = 384
_WORD = re.compile(r"\S+")


class WhitespaceTokenizer:
    """One token per whitespace-separated word, with exact character offsets."""

    name = "test-whitespace"

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        return [(m.start(), m.end()) for m in _WORD.finditer(text)]


class HashingEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words get higher cosine similarity."""

    model_name = "test-hashing-embedder"
    dimension = DIMENSION
    is_loaded = True
    load_error: str | None = None

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        vector = [0.0] * DIMENSION
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(word.encode()).hexdigest(), 16) % DIMENSION
            vector[index] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def warm_up(self) -> None:
        return None

    def tokenizer(self) -> Tokenizer:
        return WhitespaceTokenizer()


def make_pdf(pages: list[str]) -> bytes:
    """Build a real PDF with one text block per page."""
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text, fontsize=10)
    data: bytes = document.tobytes()
    document.close()
    return data


def synthetic_metadata(
    arxiv_id: str, version: int = 1, title: str = "Synthetic Paper"
) -> ArxivMetadata:
    return ArxivMetadata(
        arxiv_id=arxiv_id,
        version=version,
        title=title,
        authors=["Test Author"],
        abstract="Synthetic abstract for tests.",
        categories=["cs.CL"],
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        updated_at=datetime(2020, 1, 2, tzinfo=UTC),
    )


class FakeArxiv:
    """In-memory arXiv source keyed by base ID."""

    def __init__(self) -> None:
        self.papers: dict[str, tuple[ArxivMetadata, bytes]] = {}
        self.downloads = 0

    def add(self, metadata: ArxivMetadata, pdf: bytes) -> None:
        self.papers[metadata.arxiv_id] = (metadata, pdf)

    def fetch_metadata(self, arxiv_id: ArxivId) -> ArxivMetadata:
        from app.core.errors import NotFoundError

        if arxiv_id.base not in self.papers:
            raise NotFoundError(f"arXiv has no paper with identifier {arxiv_id}")
        return self.papers[arxiv_id.base][0]

    def download_pdf(self, arxiv_id: str, version: int, max_bytes: int) -> bytes:
        self.downloads += 1
        return self.papers[arxiv_id][1]


class FakeProvider:
    """Scripted stand-in for the local LLM. Records every request it receives."""

    model_name = "test-fake-llm"

    def __init__(self, responses: list[str] | None = None, error: Exception | None = None) -> None:
        self.options: dict[str, object] = {"num_ctx": 4096, "temperature": 0.0}
        self.responses = list(responses or [])
        self.error = error
        self.requests: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        text = (
            self.responses.pop(0)
            if self.responses
            else '{"status":"insufficient_evidence","claims":[]}'
        )
        return GenerationResult(
            text=text,
            model=self.model_name,
            prompt_tokens=100,
            completion_tokens=20,
            duration_ms=1.0,
            truncated=False,
        )


def answer_json(*claims: tuple[str, list[str]], status: str = "answered") -> str:
    return json.dumps(
        {"status": status, "claims": [{"text": t, "citations": c} for t, c in claims]}
    )


def make_test_container(
    settings: Settings,
    sessions: sessionmaker[Session],
    storage: Path,
    arxiv: FakeArxiv | None = None,
    provider: FakeProvider | None = None,
    chunking: ChunkingConfig | None = None,
) -> Container:
    embedder = HashingEmbedder()
    ingestion = IngestionService(
        sessions,
        arxiv or FakeArxiv(),
        embedder,
        WhitespaceTokenizer,
        FileStore(storage),
        chunking or ChunkingConfig(256, 38),
        max_pdf_bytes=5 * 1024 * 1024,
        max_pdf_pages=10,
    )
    search = SearchService(sessions, embedder, settings.search_max_top_k)
    return Container(
        settings=settings,
        session_factory=sessions,
        embedder=embedder,
        ingestion=ingestion,
        search=search,
        corpus=CorpusService(sessions),
        runner=JobRunner(1, ingestion.run_job),
        qa=QAService(sessions, search, provider or FakeProvider(), qa_limits(settings)),
    )
