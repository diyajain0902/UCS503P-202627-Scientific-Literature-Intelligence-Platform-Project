"""Page-aware PDF text extraction with PyMuPDF (FR-04).

The extracted document text is the page texts joined by ``PAGE_SEPARATOR``. Chunk character offsets
refer to this text, which is reproducible from the same PDF bytes and ``EXTRACTOR_VERSION``.
"""

import bisect
import unicodedata
from dataclasses import dataclass

import pymupdf

from app.core.errors import DocumentRejectedError

EXTRACTOR_VERSION = f"pymupdf-{pymupdf.VersionBind}/v1"
PAGE_SEPARATOR = "\n\n"
_MIN_CHARS_PER_PAGE = 50


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    page_starts: tuple[int, ...]
    """Character offset in ``text`` where each page (1-based page = index + 1) begins."""

    @property
    def page_count(self) -> int:
        return len(self.page_starts)

    def page_at(self, offset: int) -> int:
        """1-based page number containing character ``offset``."""
        if not 0 <= offset < max(len(self.text), 1):
            raise ValueError(f"offset {offset} outside document text")
        return bisect.bisect_right(self.page_starts, offset)


def _normalize(page_text: str) -> str:
    text = unicodedata.normalize("NFC", page_text).replace("\x00", "")
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_pdf(data: bytes, max_pages: int) -> ExtractedDocument:
    """Validate and extract text page by page. Raises ``DocumentRejectedError`` with a
    user-readable reason.
    """
    if not data.startswith(b"%PDF-"):
        raise DocumentRejectedError("File is not a PDF (missing %PDF- header)")
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several unrelated types for corrupt input
        raise DocumentRejectedError("PDF is corrupt or unreadable") from exc

    with document:
        if document.needs_pass or document.is_encrypted:
            raise DocumentRejectedError("PDF is encrypted or password-protected")
        if document.page_count == 0:
            raise DocumentRejectedError("PDF has no pages")
        if document.page_count > max_pages:
            raise DocumentRejectedError(
                f"PDF has {document.page_count} pages; the limit is {max_pages}"
            )
        try:
            pages = [
                _normalize(document.load_page(index).get_text("text"))
                for index in range(document.page_count)
            ]
        except Exception as exc:
            raise DocumentRejectedError("Text extraction failed for this PDF") from exc

    total_chars = sum(len(page) for page in pages)
    if total_chars < _MIN_CHARS_PER_PAGE * len(pages):
        raise DocumentRejectedError(
            "PDF has little or no extractable text (likely scanned); OCR is not supported"
        )

    page_starts: list[int] = []
    parts: list[str] = []
    cursor = 0
    for index, page in enumerate(pages):
        if index:
            parts.append(PAGE_SEPARATOR)
            cursor += len(PAGE_SEPARATOR)
        page_starts.append(cursor)
        parts.append(page)
        cursor += len(page)
    return ExtractedDocument(text="".join(parts), page_starts=tuple(page_starts))
