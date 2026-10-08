# Requirements Traceability Matrix

Status values: **Verified** (passing test/eval evidence) · **Implemented, unverified** · **Partial** · **Blocked** · **Planned** · **Deferred**.
Update this file in the same change that alters a requirement's implementation or tests.

Last updated: 2026-10-08 (Milestone 3).

| Req | Milestone | Module(s) | Tests / evidence | Metric | Status |
|-----|-----------|-----------|------------------|--------|--------|
| FR-01 | M1, M4 | `backend/app/ingestion/arxiv.py` | `test_arxiv.py` (ID parsing, Atom parsing, SSRF allow-list, redirects, size cap, rate limit, error mapping); `test_arxiv_live.py` (live, manual) | — | Partial — import by ID verified (incl. live arXiv 2026-10-08); query search UI is M4 |
| FR-02 | M1 | `backend/app/services/ingestion.py`, `backend/app/db/` | `test_ingestion_pipeline.py` (ready path, idempotent re-import, new version replaces, retry) — CI integration job; real end-to-end import of 1706.03762v7 on local PostgreSQL (progress log) | — | Verified (CI + local real-component run) |
| FR-03 | M4 | `backend/app/ingestion/upload.py` | — | — | Planned |
| FR-04 | M1 | `backend/app/ingestion/pdf.py` | `test_pdf.py` (offsets, page mapping, determinism, non-PDF/corrupt/encrypted/too-many-pages/no-text rejection) | — | Verified |
| FR-05 | M1 | `backend/app/ingestion/chunking.py` | `test_chunking.py`; `test_real_model.py::test_real_tokenizer_chunks_fit_model_input` | NFR-08 | Verified (ADR-0003: 256/38) |
| FR-06 | M1 | `backend/app/retrieval/embedding.py` | `test_embedding.py`; `test_real_model.py` (384-dim, normalized, max_seq_length 256); DB rejects ≠384 dims | — | Verified |
| FR-07 | M1 | `backend/app/db/models.py`, `backend/alembic/versions/20261008_0001_initial_schema.py` | `test_db_schema.py` (upgrade, downgrade/upgrade, `alembic check` drift, constraints, cascade) — CI integration job | — | Verified (CI, real PostgreSQL + pgvector 0.8.0) |
| FR-08 | M1 | `backend/app/retrieval/search.py`, `backend/app/services/search.py`, `backend/app/api/v1/routes.py`, `frontend/src/features/search/` | `test_search_integration.py` (ranking, filter, determinism, empty corpus); `test_api_validation.py` (bounds); `test_pgvector_version.py`; `SearchPanel.test.tsx` | NFR-01, NFR-04 | Verified (CI + local Compose, pgvector 0.8.0; real-model manual queries); requires pgvector ≥ 0.8.0 (guarded); retrieval quality unmeasured until M3 |
| FR-09 | M2 | `backend/app/generation/` (`ollama.py`, `prompts.py`, `provider.py`), `backend/app/services/qa.py`, `backend/app/api/v1/qa.py`, `frontend/src/features/qa/` | `test_generation.py` (prompt, schema, adapter); `test_qa_integration.py` (mocked model, real DB); `test_qa_ollama.py` (real qwen2.5:3b); `QAPanel.test.tsx`; manual real-paper run (progress log) | NFR-03 | Verified (mocked + real model); answer quality not yet evaluated (M3) |
| FR-10 | M2 | `backend/app/generation/citations.py`, `answer_citations` table | `test_generation.py` (valid/invalid/duplicate/label-only); `test_qa_integration.py` (fabricated labels stored invalid, never linked) | NFR-06 | Verified (deterministic citation validity); semantic support not verified |
| FR-11 | M2 | `backend/app/services/qa.py` | `test_qa_integration.py` (below threshold without model call; model abstains; no valid citations withheld); `test_qa_ollama.py`; real-paper run 2/2 unanswerable abstained | NFR-07 | Verified on smoke sets; threshold provisional (M3) |
| FR-12 | M5 | `backend/app/services/summaries.py` | — | — | Planned |
| FR-13 | M5 | `backend/app/services/summaries.py` | — | — | Planned |
| FR-14 | M5 | `backend/app/services/extraction.py` | — | — | Planned |
| FR-15 | M5 | `backend/app/services/comparison.py` | — | — | Planned |
| FR-16 | M4 | `backend/app/services/corpus.py`, `backend/app/api/v1/routes.py`, `frontend/src/features/corpus/` | `test_search_integration.py` (list papers); `PaperList.test.tsx` | — | Partial — list + detail endpoints and list UI; filters/delete are M4 |
| FR-17 | M1, M4 | `backend/app/services/ingestion.py`, `backend/app/services/jobs.py`, `frontend/src/features/ingest/` | `test_ingestion_pipeline.py` (states, actionable errors, crash rollback, interrupted jobs, single in-flight job); `ImportForm.test.tsx` | — | Partial — states/errors/retry-by-reimport verified; retry button UI is M4 |
| FR-18 | M2, M4 | `queries`, `answers`, `answer_evidence`, `answer_citations` (migration 0002); `GET /api/v1/qa`, `GET /api/v1/qa/{id}` | `test_qa_integration.py` (persisted provenance, history order, errors recorded, survives paper deletion) | NFR-09 | Partial — persistence + API verified; history UI is M4 |
| FR-19 | M3 | `backend/app/evaluation/` (`dataset.py`, `metrics.py`, `corpus.py`, `runner.py`, `__main__.py`), `eval/corpus.json`, `eval/qa_v1.json`, `eval/runs/` | `test_eval_metrics.py` (hand-computed); `test_eval_integration.py` (corpus verify, label check, runs, records); baseline runs | NFR-01, NFR-02 | Verified (tooling); labels AI-written, unreviewed (ADR-0007) |
| FR-20 | M3, M5 | `backend/app/evaluation/runner.py::run_qa` | `test_eval_integration.py::test_qa_run_and_record`; baseline Q&A runs | NFR-03, NFR-06, NFR-07 | Partial — citation validity, cited-relevant, abstention, latency measured; semantic groundedness is M5 |
| FR-21 | M3 | `.github/workflows/ci.yml` (`retrieval-eval`) | CI job builds corpus from arXiv and gates Recall@5 ≥ 0.675 | NFR-01 | Implemented; first CI result recorded in progress log |
| FR-22 | M4 | `frontend/src/features/dashboard/` | — | — | Planned |
| FR-23 | M4 | `frontend/src/features/settings/` | — | — | Planned |
| FR-24 | M6 | `backend/app/retrieval/` | — | NFR-01 | Planned |
| FR-25 | M6 | `backend/app/retrieval/` | — | NFR-01, NFR-03 | Planned |
| FR-26 | — | — | — | — | Deferred (scanned PDFs rejected per AC-03.3) |
| IR-01 | M0+ | `backend/app/main.py`, `backend/app/api/v1/`, `backend/app/core/errors.py` | `test_health.py`; `test_api_validation.py` (error envelope, pagination bounds); 404 envelope in `test_search_integration.py` | — | Verified |
| IR-02 | M0 | `backend/app/core/config.py`, `.env.example`, `.gitignore` | `tests/test_config.py` (4 tests) | — | Verified |
| IR-03 | M1 | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` | CI `docker-images` job; local `docker compose up` with end-to-end import + search via nginx (progress log 2026-10-08) | — | Verified |
| IR-04 | M0 | `.github/workflows/ci.yml` | Green runs on PR #2, `main`, and `feature/m1-vertical-slice` (4 jobs) | NFR-14 | Verified |
| IR-05 | M0, M1, M2 | `backend/app/api/v1/health.py`, `backend/app/services/health.py`, `frontend/src/features/status/` | `test_api_validation.py::test_ready_reports_each_dependency_and_fails_without_database`; `test_search_integration.py::test_ready_with_database_and_without_ollama`; `BackendStatus.test.tsx` | — | Verified |
| IR-06 | M1 | `backend/app/core/logging.py` | `test_api_validation.py::test_request_id_header` | NFR-11 | Implemented, partially verified — JSON formatter not unit-tested; logs carry IDs/sizes only by design |
| IR-07 | M2 | `backend/app/generation/ollama.py`, `provider.py` | `test_generation.py` (options, schema, unreachable 503, missing model 503, timeout 504, bad output 502, truncation flag, warm-up) | NFR-16 | Verified |
| IR-08 | M1 | `backend/app/services/jobs.py` (ADR-0005) | `test_search_integration.py` (HTTP import runs in background, polled to ready) | — | Verified |
| IR-09 | Ongoing | `README.md`, `docs/` | — | — | Partial |
| NFR-10 | M0, M1 | `backend/app/main.py`, `backend/app/ingestion/arxiv.py`, `backend/app/ingestion/storage.py`, `docker-compose.yml` | CORS test; SSRF allow-list + redirect tests; storage path-traversal tests; parameterized SQL via ORM; defusedxml entity test; localhost-only ports | — | Partial — upload controls (M4) and security audit pending |
| NFR-16 | M2 | `backend/app/services/qa.py`, `backend/app/api/v1/health.py` | `test_qa_integration.py::test_generation_failures_are_explicit_and_recorded` (search still 200 while generation fails) | — | Verified |
| NFR-08 | M1 | `backend/app/ingestion/` | determinism tests for extraction, chunk text and IDs; deterministic search ordering (tie-break on chunk ID) | — | Partial — retrieval-ranking reproducibility on eval set in M3 |
| NFR-12 | M1 | `backend/app/core/config.py` | size/page caps, top_k/query/pagination bounds tested | — | Partial — generation bounds M2, upload M4 |
| NFR-15 | M0+ | `frontend/src/features/` | Role/label-based queries in all component tests; responsive grid; sr-only status text | — | Partial — no manual accessibility audit yet |

Planned module paths are indicative and will be corrected here when code lands.

## Non-functional targets measured in M3

| NFR | Target | Measured (M3 baseline) | Status |
|-----|--------|------------------------|--------|
| NFR-01 | Recall@5 ≥ 0.80 | 0.700 | **Not met** |
| NFR-02 | MRR reported | 0.416 | Verified (reported) |
| NFR-03 | p95 Q&A ≤ 3 s | 2.74 s (AC, one run); 7.24 s (battery); cold 5.9–10.5 s | Not established — depends on power state; more runs needed |
| NFR-04 | Search p95 reported | 53 ms | Verified (reported) |
| NFR-06 | 100% displayed citations valid | 1.00 citation validity in all runs | Verified on eval set |
| NFR-07 | Abstention reported | recall 1.00, precision 0.50–0.59, false answers 0/10 | Verified (reported) |
