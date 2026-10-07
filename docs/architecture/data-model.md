# Data Model (planned — implemented via Alembic in M1+)

Extends the proposal's four tables (`papers`, `chunks`, `queries`, `answers`) with documents, jobs, citations,
and evaluation records so that provenance and job state are explicit. Columns are indicative; migrations are the
source of truth once written.

| Table | Key columns | Constraints / notes | Milestone |
|-------|-------------|---------------------|-----------|
| `papers` | `id` (UUID), `source` (`arxiv`/`upload`), `arxiv_id`, `arxiv_version`, `title`, `authors` (JSONB), `abstract`, `categories`, `published_at`, `created_at`, `updated_at` | `UNIQUE(arxiv_id)` where not null; `CHECK(source IN …)` | M1 |
| `documents` | `id`, `paper_id` FK, `sha256`, `storage_key` (server-generated), `page_count`, `byte_size`, `extractor_version` | `UNIQUE(sha256)`; `ON DELETE CASCADE` from paper | M1 |
| `chunks` | `id` (deterministic: hash of document sha256 + chunker version + ordinal), `document_id` FK, `ordinal`, `page_start`, `page_end`, `char_start`, `char_end`, `text`, `token_count`, `embedding vector(384)`, `chunker_version` | `UNIQUE(document_id, ordinal)`; `CHECK(page_start <= page_end)`; HNSW index `vector_cosine_ops` | M1 |
| `ingestion_jobs` | `id`, `paper_id` FK nullable, `kind`, `state`, `error`, `attempts`, timestamps | `CHECK(state IN …)` | M1 |
| `queries` | `id`, `question`, `filters` (JSONB), `retrieval_config` (JSONB), `latency_ms`, `created_at` | — | M2 |
| `answers` | `id`, `query_id` FK, `status` (`answered`/`insufficient_evidence`/`error`), `answer_text`, `model`, `prompt_version`, `generation_ms` | `CHECK(status IN …)` | M2 |
| `answer_citations` | `answer_id` FK, `chunk_id` FK, `claim_index`, `valid` | Replaces proposal's `cited_chunk_ids` array to keep FK integrity | M2 |
| `extractions` | `id`, `paper_id` FK, `field`, `value`, `evidence_chunk_ids`, `model`, `prompt_version` | M5 |
| `eval_runs` | `id`, `dataset_version`, `config` (JSONB), `git_sha`, `metrics` (JSONB), `created_at` | Also written as JSON files under `eval/runs/` | M3 |

## Deletion semantics

Deleting a paper cascades to documents, chunks, and extractions, and deletes stored files. Historical
`answer_citations` referencing deleted chunks: `ON DELETE SET NULL` on `chunk_id` with the citation's resolved
paper title/page snapshot retained, so query history stays readable. Final choice recorded in an ADR in M2.
