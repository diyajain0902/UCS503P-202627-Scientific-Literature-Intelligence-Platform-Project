# Acceptance Criteria

Each criterion `AC-<req>.<n>` must be verifiable by an automated test, an evaluation run, or a documented manual check.
"Mocked" tests use controlled substitutes; "integration" tests (pytest marker `integration`) use real services.

## Ingestion

**FR-01 arXiv discovery**
- AC-01.1 A valid arXiv ID (new or old style, with or without version) returns normalized metadata; an invalid ID returns HTTP 422.
- AC-01.2 Outbound requests go only to configured arXiv hosts over HTTPS, with timeout and rate limiting per arXiv API terms (SSRF guard).
- AC-01.3 arXiv unavailability returns an actionable error, not a crash.

**FR-02 arXiv import**
- AC-02.1 Importing a paper creates exactly one `papers` row; a second import of the same `arxiv_id` creates no duplicate (DB unique constraint + test).
- AC-02.2 Re-import of a newer version updates metadata and re-chunks; the version used is recorded.

**FR-03 PDF upload**
- AC-03.1 Files over the configured size or page limit are rejected (HTTP 413/422) before full processing.
- AC-03.2 Non-PDF content (by magic bytes, not just extension), encrypted PDFs, and corrupt PDFs are rejected with specific messages.
- AC-03.3 PDFs with no extractable text layer are rejected with "scanned PDF — OCR not supported".
- AC-03.4 Stored filenames are server-generated; user-supplied names never form a filesystem path (path-traversal test).
- AC-03.5 Identical file content (SHA-256) is detected and not ingested twice.

**FR-04 Extraction**
- AC-04.1 Extracted text carries 1-based page numbers and character offsets that reproduce the text when sliced.
- AC-04.2 One malformed page or document fails its job only; other documents in a batch complete.

**FR-05 Chunking**
- AC-05.1 Running the chunker twice on the same input and config yields byte-identical chunks and identical chunk IDs.
- AC-05.2 Chunk size and overlap follow the documented config (ADR-0003) and never exceed the embedding model's input limit.
- AC-05.3 A chunk crossing a page boundary records `page_start` and `page_end`; offsets map back to the source text.
- AC-05.4 Chunker config (tokenizer, window, overlap, version) is stored with each document's chunks.

**FR-06 Embeddings**
- AC-06.1 Every stored vector has dimension 384 (enforced by `vector(384)` column and a runtime check).
- AC-06.2 Embedding runs locally; no network call at inference time after the model is cached.
- AC-06.3 Embeddings are L2-normalized and batched.

**FR-07 Persistence**
- AC-07.1 Schema is created only via Alembic migrations; `alembic upgrade head` on an empty DB succeeds; downgrade of the latest migration succeeds.
- AC-07.2 Foreign keys, NOT NULL, UNIQUE constraints exist as specified in `docs/architecture/data-model.md`.
- AC-07.3 Deleting a paper deletes its documents, chunks, and stored files (deliberate cascade), and is tested.

**FR-17 Jobs**
- AC-17.1 Each ingestion has a job row with an explicit state; failures record a user-readable error.
- AC-17.2 A failed job can be retried safely without duplicating chunks.

## Retrieval and answering

**FR-08 Semantic search**
- AC-08.1 Results include chunk ID, paper ID/title, page range, passage text, and similarity score, ordered by score.
- AC-08.2 `top_k` is bounded (configurable max); query length is bounded.
- AC-08.3 On a fixed fixture corpus, a known query ranks the expected chunk first (deterministic test).
- AC-08.4 Search works while Ollama is unavailable.

**FR-09 Grounded Q&A**
- AC-09.1 The prompt contains only retrieved passages as evidence, clearly delimited and labelled as untrusted.
- AC-09.2 The model is called with explicit timeout, max tokens, temperature, and context size from config.
- AC-09.3 Model output is parsed into a validated schema; malformed output yields an explicit error state, not a fabricated answer.
- AC-09.4 Ollama down, model missing, and timeout each map to distinct, documented errors (tests with a fake provider).
- AC-09.5 Each answer records model tag, prompt version, retrieval config, and latency.

**FR-10 Citations**
- AC-10.1 Every citation ID in the output is checked against the set of chunks supplied in context; unknown IDs are flagged `invalid` and not rendered as valid.
- AC-10.2 Each valid citation resolves to paper, page(s), and the exact passage text.
- AC-10.3 Claims without any valid citation are marked `unsupported`.
- AC-10.4 Deterministic citation validity is reported separately from semantic support (groundedness).

**FR-11 Abstention**
- AC-11.1 When no retrieved passage passes the relevance threshold, the system returns `insufficient_evidence` without calling the model.
- AC-11.2 When the model reports insufficient evidence, the response is `insufficient_evidence` with retrieved passages shown for inspection.
- AC-11.3 Unanswerable eval questions are used to measure abstention (NFR-07).

**FR-18 History**
- AC-18.1 Each Q&A request persists question, answer, citations, validation status, config, and latency.

## Summaries, extraction, comparison (M5)

- AC-12.1 / AC-13.1 Summaries cite source chunks; cross-paper synthesis attributes each claim to its paper(s).
- AC-14.1 Extraction output validates against a Pydantic schema; missing fields are `unknown`, never guessed.
- AC-14.2 Each extracted value links to at least one supporting chunk, verified to exist.
- AC-15.1 Comparison flags rows where datasets, protocols, or units differ instead of ranking them directly.

## Corpus management (M4)

- AC-16.1 Paper list supports pagination and filters (source, year, category, ingestion status).
- AC-16.2 Delete requires explicit confirmation in the UI and removes all derived data (AC-07.3).

## Evaluation (M3)

- AC-19.1 Eval dataset is version-controlled with a schema, labeler, and labeling date per item; items are manually labeled.
- AC-19.2 Recall@k and MRR implementations pass unit tests on hand-computed examples.
- AC-19.3 Each eval run writes a record (dataset version, corpus manifest, model/config, git SHA, metrics, timestamp).
- AC-21.1 CI fails if Recall@5 falls below the documented threshold on the fixed eval corpus.

## Infrastructure

- AC-IR01.1 All endpoints are under `/api/v1`; OpenAPI is served at `/api/v1/openapi.json`. *(M0: verified by test)*
- AC-IR02.1 Settings load from `SLIP_`-prefixed env vars; invalid values fail fast. *(M0: verified by test)*
- AC-IR04.1 CI runs backend lint, format, mypy, tests and frontend lint, typecheck, tests, build on PRs. *(M0: workflow added)*
- AC-IR05.1 `GET /api/v1/health` returns status and version. *(M0: verified by test)*
- AC-IR05.2 `GET /api/v1/ready` reports DB, embedder, and Ollama individually. *(M1/M2)*
