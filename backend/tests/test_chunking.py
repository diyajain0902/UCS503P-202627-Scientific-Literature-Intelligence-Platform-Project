import pytest

from app.ingestion.chunking import ChunkingConfig, chunk_document
from app.ingestion.pdf import PAGE_SEPARATOR, ExtractedDocument
from tests.fakes import WhitespaceTokenizer

SHA = "a" * 64


def _document(pages: list[str]) -> ExtractedDocument:
    starts, cursor = [], 0
    for index, page in enumerate(pages):
        if index:
            cursor += len(PAGE_SEPARATOR)
        starts.append(cursor)
        cursor += len(page)
    return ExtractedDocument(text=PAGE_SEPARATOR.join(pages), page_starts=tuple(starts))


def _words(prefix: str, count: int) -> str:
    return " ".join(f"{prefix}{i}" for i in range(count))


def test_windows_respect_size_and_overlap() -> None:
    config = ChunkingConfig(window_tokens=12, overlap_tokens=3)  # 10 content tokens, stride 7
    doc = _document([_words("w", 30)])
    chunks = chunk_document(doc, SHA, WhitespaceTokenizer(), config)
    assert [c.token_count for c in chunks] == [10, 10, 10, 9]
    assert chunks[0].text.split()[-3:] == chunks[1].text.split()[:3]
    assert chunks[-1].text.split()[-1] == "w29"  # every token covered


def test_chunk_text_is_exact_source_substring() -> None:
    doc = _document([_words("a", 15), _words("b", 15)])
    for chunk in chunk_document(doc, SHA, WhitespaceTokenizer(), ChunkingConfig(10, 2)):
        assert doc.text[chunk.char_start : chunk.char_end] == chunk.text


def test_chunk_spanning_pages_records_both_pages() -> None:
    doc = _document([_words("a", 6), _words("b", 6)])
    chunks = chunk_document(doc, SHA, WhitespaceTokenizer(), ChunkingConfig(10, 2))
    assert (chunks[0].page_start, chunks[0].page_end) == (1, 2)
    assert (chunks[-1].page_start, chunks[-1].page_end) == (2, 2)


def test_chunking_is_deterministic_including_ids() -> None:
    doc = _document([_words("a", 50)])
    config = ChunkingConfig(16, 4)
    first = chunk_document(doc, SHA, WhitespaceTokenizer(), config)
    second = chunk_document(doc, SHA, WhitespaceTokenizer(), config)
    assert first == second
    assert len({c.id for c in first}) == len(first)


def test_ids_change_with_document_or_config() -> None:
    doc = _document([_words("a", 50)])
    base = chunk_document(doc, SHA, WhitespaceTokenizer(), ChunkingConfig(16, 4))
    other_doc = chunk_document(doc, "b" * 64, WhitespaceTokenizer(), ChunkingConfig(16, 4))
    other_cfg = chunk_document(doc, SHA, WhitespaceTokenizer(), ChunkingConfig(16, 5))
    assert base[0].id != other_doc[0].id
    assert base[0].id != other_cfg[0].id


def test_short_and_empty_documents() -> None:
    assert chunk_document(_document([""]), SHA, WhitespaceTokenizer(), ChunkingConfig(16, 4)) == []
    single = chunk_document(
        _document(["one two"]), SHA, WhitespaceTokenizer(), ChunkingConfig(16, 4)
    )
    assert len(single) == 1 and single[0].text == "one two"


def test_default_config_matches_adr_0003() -> None:
    config = ChunkingConfig(256, 38)
    assert config.content_tokens == 254
    assert config.stride == 216
    assert config.version("tok") == "tokwin-v1|tok|w256|o38"


@pytest.mark.parametrize(("window", "overlap"), [(2, 0), (12, 10), (12, -1)])
def test_invalid_configs_rejected(window: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        ChunkingConfig(window, overlap)
