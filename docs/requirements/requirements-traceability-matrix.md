# Requirements Traceability Matrix

Status values: **Verified** (passing test/eval evidence) · **Implemented, unverified** · **Partial** · **Blocked** · **Planned** · **Deferred**.
Update this file in the same change that alters a requirement's implementation or tests.

Last updated: 2026-10-08 (Milestone 0).

| Req | Milestone | Module(s) | Tests / evidence | Metric | Status |
|-----|-----------|-----------|------------------|--------|--------|
| FR-01 | M1, M4 | `backend/app/ingestion/arxiv.py` | — | — | Planned |
| FR-02 | M1 | `backend/app/services/ingestion.py`, `backend/app/db/` | — | — | Planned |
| FR-03 | M4 | `backend/app/ingestion/upload.py` | — | — | Planned |
| FR-04 | M1 | `backend/app/ingestion/pdf.py` | — | — | Planned |
| FR-05 | M1 | `backend/app/ingestion/chunking.py` | — | NFR-08 | Planned |
| FR-06 | M1 | `backend/app/retrieval/embedding.py` | — | — | Planned |
| FR-07 | M1 | `backend/app/db/`, `backend/alembic/` | — | — | Planned |
| FR-08 | M1 | `backend/app/retrieval/search.py`, `backend/app/api/v1/search.py` | — | NFR-01, NFR-04 | Planned |
| FR-09 | M2 | `backend/app/generation/`, `backend/app/services/qa.py` | — | NFR-03 | Planned |
| FR-10 | M2 | `backend/app/generation/citations.py` | — | NFR-06 | Planned |
| FR-11 | M2 | `backend/app/services/qa.py` | — | NFR-07 | Planned |
| FR-12 | M5 | `backend/app/services/summaries.py` | — | — | Planned |
| FR-13 | M5 | `backend/app/services/summaries.py` | — | — | Planned |
| FR-14 | M5 | `backend/app/services/extraction.py` | — | — | Planned |
| FR-15 | M5 | `backend/app/services/comparison.py` | — | — | Planned |
| FR-16 | M4 | `backend/app/api/v1/papers.py`, `frontend/src/features/corpus/` | — | — | Planned |
| FR-17 | M1, M4 | `backend/app/services/jobs.py` | — | — | Planned |
| FR-18 | M2, M4 | `backend/app/db/`, `frontend/src/features/history/` | — | NFR-09 | Planned |
| FR-19 | M3 | `backend/app/evaluation/`, `eval/` | — | NFR-01, NFR-02 | Planned |
| FR-20 | M3, M5 | `backend/app/evaluation/` | — | NFR-03, NFR-06, NFR-07 | Planned |
| FR-21 | M3 | `.github/workflows/ci.yml` | — | NFR-01 | Planned |
| FR-22 | M4 | `frontend/src/features/dashboard/` | — | — | Planned |
| FR-23 | M4 | `frontend/src/features/settings/` | — | — | Planned |
| FR-24 | M6 | `backend/app/retrieval/` | — | NFR-01 | Planned |
| FR-25 | M6 | `backend/app/retrieval/` | — | NFR-01, NFR-03 | Planned |
| FR-26 | — | — | — | — | Deferred (scanned PDFs rejected per AC-03.3) |
| IR-01 | M0+ | `backend/app/main.py`, `backend/app/api/v1/` | `tests/test_health.py::test_openapi_schema_is_versioned` | — | Partial — versioning verified; error envelope and pagination in M1 |
| IR-02 | M0 | `backend/app/core/config.py`, `.env.example`, `.gitignore` | `tests/test_config.py` (4 tests) | — | Verified |
| IR-03 | M1 | `docker-compose.yml` | — | — | Blocked — Docker not installed on reference machine |
| IR-04 | M0 | `.github/workflows/ci.yml` | Local equivalent of every CI step passed; first remote run pending PR | NFR-14 | Implemented, unverified |
| IR-05 | M0, M1, M2 | `backend/app/api/v1/health.py` | `tests/test_health.py::test_health_reports_ok_and_version` | — | Partial — liveness verified; readiness planned |
| IR-06 | M1 | `backend/app/core/logging.py` | — | NFR-11 | Planned |
| IR-07 | M2 | `backend/app/generation/ollama.py` | Manual probe only (see progress log) | NFR-16 | Planned |
| IR-08 | M1 | `backend/app/services/jobs.py` | — | — | Planned |
| IR-09 | Ongoing | `README.md`, `docs/` | — | — | Partial |
| NFR-10 (CORS) | M0 | `backend/app/main.py` | `tests/test_health.py::test_cors_allows_only_configured_origin` | — | Partial — CORS allow-list verified; other controls planned |
| NFR-15 | M0+ | `frontend/src/App.tsx` | `frontend/src/App.test.tsx` (role="status" region, error state) | — | Partial |

Planned module paths are indicative and will be corrected here when code lands.
