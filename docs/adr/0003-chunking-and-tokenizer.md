# ADR-0003: Chunk size must respect the embedding model's input limit

- Status: **Accepted** (approved by the team 2026-10-08, before M1 implementation)
- Date: 2026-10-08

## Context

The proposal specifies ≈500-token chunks with ≈15% overlap. The required embedding model,
`sentence-transformers/all-MiniLM-L6-v2`, is documented on its model card as truncating input longer than
256 word pieces (its `max_seq_length` is 256; it was trained on 128-token inputs). A 500-token chunk would
therefore be embedded from roughly its first half only, silently hiding the rest of the chunk from retrieval.
**Verified 2026-10-08:** after download, `SentenceTransformer(...).max_seq_length == 256`, tokenizer
`model_max_length == 256`, embedding dimension 384 (`tests/test_real_model.py::test_model_limits_match_adr_0003`).

## Options

1. **Embedding-aligned chunks:** ~256 MiniLM word-piece tokens per chunk (hard cap 256 including special tokens,
   so ~250 content tokens), ~15% overlap (~38 tokens). Every token is embedded. More chunks per paper.
2. **Proposal size, truncated embedding:** 500-token chunks; accept that only the first ~254 tokens are embedded.
   Simple, but retrieval misses content and the loss is invisible.
3. **Small-to-big:** embed ~256-token child chunks for retrieval, pass the enclosing ~500-token parent window to
   the LLM. Best of both, more complexity.

## Decision

Adopt **option 1** as the M1 baseline: tokenizer = the embedding model's own WordPiece tokenizer (so token counts
match what is embedded), window 256 tokens including special tokens, overlap 38 tokens, chunks built over the
page-concatenated text with page boundaries tracked by character offsets. Chunker config is versioned and stored
with chunks. Option 3 is a candidate experiment for M6, adopted only if it improves eval metrics.

This is a documented deviation from the proposal's "≈500 tokens" baseline, justified by the model's input limit.

## Consequences

- Roughly twice as many chunks and vectors as the proposal implied; fine at a few hundred papers.
- Shorter LLM context per chunk; top-k may need to increase (bounded by Ollama `num_ctx`).

## Implementation notes (M1)

- `app/ingestion/chunking.py`: window 256 includes `[CLS]`/`[SEP]`, so 254 content tokens; stride 216.
- Chunk text is the exact source substring between the first and last token offsets; re-tokenizing it never exceeds
  254 tokens (verified on 400 synthetic sentences with the real tokenizer).
- Chunker version string stored per document, e.g. `tokwin-v1|sentence-transformers/all-MiniLM-L6-v2|w256|o38`.
- The embedder refuses to load if `max_seq_length` < the configured window (fails loudly instead of truncating).
