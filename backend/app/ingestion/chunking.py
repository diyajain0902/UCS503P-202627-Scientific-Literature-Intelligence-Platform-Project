"""Deterministic token-window chunking (FR-05, ADR-0003).

Chunks are windows over the embedding model's own tokenization of the whole extracted document, so
every chunk fits the model's input limit. Chunk text is the exact source substring between the first
and last token's character offsets, which keeps provenance exact. Chunk IDs are UUIDv5 values
derived from the document hash, chunker version, and ordinal, so re-chunking the same document with
the same config reproduces the same IDs.
"""

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.ingestion.pdf import ExtractedDocument

CHUNKER_ALGORITHM_VERSION = "1"
_CHUNK_ID_NAMESPACE = uuid.UUID("6f0a3a4e-2f43-4d0c-9a51-6c1f6e1b8d10")

# The embedding model wraps each input in [CLS] ... [SEP].
SPECIAL_TOKENS_PER_INPUT = 2


class Tokenizer(Protocol):
    name: str

    def token_spans(self, text: str) -> list[tuple[int, int]]:
        """Character spans of the content tokens of ``text`` (no special tokens)."""
        ...


@dataclass(frozen=True)
class ChunkingConfig:
    window_tokens: int
    overlap_tokens: int

    def __post_init__(self) -> None:
        if self.content_tokens <= 0:
            raise ValueError("window too small for special tokens")
        if not 0 <= self.overlap_tokens < self.content_tokens:
            raise ValueError("overlap must be non-negative and smaller than the content window")

    @property
    def content_tokens(self) -> int:
        return self.window_tokens - SPECIAL_TOKENS_PER_INPUT

    @property
    def stride(self) -> int:
        return self.content_tokens - self.overlap_tokens

    def version(self, tokenizer_name: str) -> str:
        return (
            f"tokwin-v{CHUNKER_ALGORITHM_VERSION}|{tokenizer_name}"
            f"|w{self.window_tokens}|o{self.overlap_tokens}"
        )


@dataclass(frozen=True)
class ChunkSpec:
    id: uuid.UUID
    ordinal: int
    char_start: int
    char_end: int
    page_start: int
    page_end: int
    token_count: int
    text: str


def chunk_document(
    document: ExtractedDocument,
    document_sha256: str,
    tokenizer: Tokenizer,
    config: ChunkingConfig,
) -> list[ChunkSpec]:
    spans = tokenizer.token_spans(document.text)
    if not spans:
        return []
    version = config.version(tokenizer.name)
    chunks: list[ChunkSpec] = []
    start = 0
    while True:
        window = spans[start : start + config.content_tokens]
        char_start, char_end = window[0][0], window[-1][1]
        ordinal = len(chunks)
        chunks.append(
            ChunkSpec(
                id=uuid.uuid5(_CHUNK_ID_NAMESPACE, f"{document_sha256}|{version}|{ordinal}"),
                ordinal=ordinal,
                char_start=char_start,
                char_end=char_end,
                page_start=document.page_at(char_start),
                page_end=document.page_at(char_end - 1),
                token_count=len(window),
                text=document.text[char_start:char_end],
            )
        )
        if start + config.content_tokens >= len(spans):
            return chunks
        start += config.stride
