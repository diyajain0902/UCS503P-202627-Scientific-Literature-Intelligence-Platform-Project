# Data Model

Implemented: migrations `0001` (M1) and `0002` (M2). Later rows are still planned.

Extends the proposal's four tables (`papers`, `chunks`, `queries`, `answers`) with documents, jobs, citations,
and evaluation records so that provenance and job state are explicit. Columns are indicative; migrations are the
source of truth once written.

| Table | Key columns | Constraints / notes | Milestone |
|-------|-------------|---------------------|-----------|
| `papers` | `id` (UUID), `source` (`arxiv`/`upload`), `arxiv_id`, `arxiv_version`, `title`, `authors` (JSONB), `abstract`, `categories`, `published_at`, `created_at`, `updated_at` | `UNIQUE(arxiv_id)` where not null; `CHECK(source IN …)` | M1 |
| `documents` | `id`, `paper_id` FK, `sha256`, `storage_key` (server-generated), `page_count`, `byte_size`, `extractor_version` | `UNIQUE(sha256)`; `ON DELETE CASCADE` from paper | M1 |
| `chunks` | `id` (deterministic: hash of document sha256 + chunker version + ordinal), `document_id` FK, `ordinal`, `page_start`, `page_end`, `char_start`, `char_end`, `text`, `token_count`, `embedding vector(384)`, `chunker_version` | `UNIQUE(document_id, ordinal)`; `CHECK(page_start <= page_end)`; HNSW index `vector_cosine_ops` | M1 |
| `ingestion_jobs` | `id`, `paper_id` FK nullable, `kind`, `state`, `error`, `attempts`, timestamps | `CHECK(state IN …)` | M1 |
| `queries` | `id`, `question`, `top_k`, `paper_ids` (JSONB), `created_at` | `CHECK(top_k >= 1)` | M2 ✔ |
| `answers` | `id`, `query_id` FK (unique), `status` (`answered`/`insufficient_evidence`/`error`), `reason`, `claims` (JSONB: index, text, support), `generation_model`, `prompt_version`, `embedding_model`, `config` (JSONB: retrieval + generation options), `retrieval_ms`, `generation_ms`, `latency_ms`, token counts | `CHECK(status IN …)`; reason required unless answered | M2 ✔ |
| `answer_evidence` | `answer_id` FK, `label` (P1..Pn), `rank`, `score`, `chunk_id` FK (SET NULL), `paper_id` FK (SET NULL), snapshot of title, arXiv ID, pages, passage text | `UNIQUE(answer_id, label)` | M2 ✔ |
| `answer_citations` | `answer_id` FK, `claim_index`, `position`, `label`, `valid`, `evidence_id` FK | `CHECK(valid = (evidence_id IS NOT NULL))`; replaces the proposal's `cited_chunk_ids` array | M2 ✔ |
| `extractions` | `id`, `paper_id` FK, `field`, `value`, `evidence_chunk_ids`, `model`, `prompt_version` | M5 |
| `eval_runs` | `id`, `dataset_version`, `config` (JSONB), `git_sha`, `metrics` (JSONB), `created_at` | Also written as JSON files under `eval/runs/` | M3 |

## Deletion semantics

Deleting a paper cascades to documents, chunks, and extractions, and deletes stored files. Q&A history is kept:
`answer_evidence.chunk_id` and `paper_id` become NULL while the snapshot (title, pages, passage text) remains, so
past answers stay inspectable (ADR-0006; tested in `test_qa_integration.py`).
