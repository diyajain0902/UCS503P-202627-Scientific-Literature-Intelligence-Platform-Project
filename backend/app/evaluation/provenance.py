"""Provenance audit: stored chunks against their original PDFs (FR-04, FR-08, NFR-08).

For every document, the stored PDF is re-read and two independent checks run per chunk:

1. **Offsets:** re-extraction reproduces ``text[char_start:char_end] == chunk.text`` and the
   recorded ``page_start``/``page_end`` (determinism of the extraction + chunking pipeline).
2. **Page text:** the chunk's opening and closing words occur in PyMuPDF's raw text of the recorded
   first and last page. This check does not use the offset arithmetic, so it catches page-numbering
   errors that (1) would reproduce consistently.
"""

import hashlib
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Chunk, Document, Paper
from app.ingestion.pdf import extract_pdf
from app.ingestion.storage import FileStore

PROBE_WORDS = 6


@dataclass
class ProvenanceReport:
    documents: int = 0
    chunks: int = 0
    multi_page_chunks: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _words(text: str) -> list[str]:
    return unicodedata.normalize("NFC", text).replace("\x00", "").split()


def _contains(haystack_words: list[str], needle: list[str]) -> bool:
    joined = " ".join(haystack_words)
    return " ".join(needle) in joined


def _documents(sessions: sessionmaker[Session]) -> Iterator[tuple[Paper, Document, list[Chunk]]]:
    with sessions() as session:
        rows = session.execute(select(Paper, Document).join(Document)).all()
        for paper, document in rows:
            chunks = list(
                session.scalars(
                    select(Chunk).where(Chunk.document_id == document.id).order_by(Chunk.ordinal)
                )
            )
            yield paper, document, chunks


def check_provenance(
    sessions: sessionmaker[Session], store: FileStore, max_pages: int
) -> ProvenanceReport:
    report = ProvenanceReport()
    for paper, document, chunks in _documents(sessions):
        name = paper.arxiv_id or str(paper.id)
        report.documents += 1
        if not store.exists(document.storage_key):
            report.problems.append(f"{name}: stored PDF missing ({document.storage_key})")
            continue
        data = store.read(document.storage_key)
        if hashlib.sha256(data).hexdigest() != document.sha256:
            report.problems.append(f"{name}: stored PDF does not match its recorded sha256")
            continue
        extracted = extract_pdf(data, max_pages)
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            raw_pages = [_words(pdf.load_page(i).get_text("text")) for i in range(pdf.page_count)]
        if extracted.page_count != document.page_count:
            report.problems.append(f"{name}: page count {extracted.page_count} != stored")
        for chunk in chunks:
            report.chunks += 1
            where = f"{name} chunk {chunk.ordinal}"
            if chunk.page_end > chunk.page_start:
                report.multi_page_chunks += 1
            if extracted.text[chunk.char_start : chunk.char_end] != chunk.text:
                report.problems.append(f"{where}: text differs from re-extraction at its span")
                continue
            expected = (
                extracted.page_at(chunk.char_start),
                extracted.page_at(chunk.char_end - 1),
            )
            if expected != (chunk.page_start, chunk.page_end):
                report.problems.append(
                    f"{where}: pages {chunk.page_start}-{chunk.page_end}, expected {expected}"
                )
                continue
            # Opening words lie on page_start, closing words on page_end (clipped to that page).
            first_page_end = (
                extracted.page_starts[chunk.page_start]
                if chunk.page_start < extracted.page_count
                else len(extracted.text)
            )
            head = _words(extracted.text[chunk.char_start : min(chunk.char_end, first_page_end)])
            last_page_start = extracted.page_starts[chunk.page_end - 1]
            tail = _words(extracted.text[max(chunk.char_start, last_page_start) : chunk.char_end])
            if not _contains(raw_pages[chunk.page_start - 1], head[:PROBE_WORDS]):
                report.problems.append(f"{where}: opening words not on page {chunk.page_start}")
            if not _contains(raw_pages[chunk.page_end - 1], tail[-PROBE_WORDS:]):
                report.problems.append(f"{where}: closing words not on page {chunk.page_end}")
    return report
