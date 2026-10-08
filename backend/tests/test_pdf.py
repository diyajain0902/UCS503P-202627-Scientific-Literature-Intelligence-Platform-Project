import pymupdf
import pytest

from app.core.errors import DocumentRejectedError
from app.ingestion.pdf import PAGE_SEPARATOR, extract_pdf
from tests.fakes import make_pdf

PAGE_ONE = "Transformers rely on self attention. " * 5
PAGE_TWO = "Recurrent networks process tokens sequentially. " * 5


def test_extracts_pages_with_offsets() -> None:
    doc = extract_pdf(make_pdf([PAGE_ONE, PAGE_TWO]), max_pages=10)
    assert doc.page_count == 2
    assert doc.page_starts[0] == 0
    first, second = doc.text.split(PAGE_SEPARATOR)
    assert "self attention" in first
    assert "sequentially" in second
    assert doc.page_starts[1] == len(first) + len(PAGE_SEPARATOR)
    assert doc.text[doc.page_starts[1] :].startswith("Recurrent")


def test_page_at_maps_offsets_to_pages() -> None:
    doc = extract_pdf(make_pdf([PAGE_ONE, PAGE_TWO]), max_pages=10)
    assert doc.page_at(0) == 1
    assert doc.page_at(doc.page_starts[1] - 1) == 1
    assert doc.page_at(doc.page_starts[1]) == 2
    assert doc.page_at(len(doc.text) - 1) == 2
    with pytest.raises(ValueError):
        doc.page_at(len(doc.text))


def test_extraction_is_deterministic() -> None:
    data = make_pdf([PAGE_ONE, PAGE_TWO])
    assert extract_pdf(data, 10) == extract_pdf(data, 10)


def test_rejects_non_pdf() -> None:
    with pytest.raises(DocumentRejectedError, match="not a PDF"):
        extract_pdf(b"<html>not a pdf</html>", 10)


def test_rejects_corrupt_pdf() -> None:
    with pytest.raises(DocumentRejectedError, match="corrupt"):
        extract_pdf(b"%PDF-1.7\n" + b"\x00garbage" * 50, 10)


def test_rejects_too_many_pages() -> None:
    with pytest.raises(DocumentRejectedError, match="limit is 2"):
        extract_pdf(make_pdf([PAGE_ONE] * 3), max_pages=2)


def test_rejects_pdf_without_text_layer() -> None:
    document = pymupdf.open()
    document.new_page()
    document.new_page()
    data = document.tobytes()
    with pytest.raises(DocumentRejectedError, match="OCR is not supported"):
        extract_pdf(data, 10)


def test_rejects_encrypted_pdf() -> None:
    source = pymupdf.open("pdf", make_pdf([PAGE_ONE]))
    data = source.tobytes(
        # Constant exists at runtime but is missing from PyMuPDF type hints.
        encryption=pymupdf.PDF_ENCRYPT_AES_256,  # type: ignore[attr-defined]
        user_pw="secret",
        owner_pw="owner",
    )
    with pytest.raises(DocumentRejectedError, match="encrypted"):
        extract_pdf(data, 10)
