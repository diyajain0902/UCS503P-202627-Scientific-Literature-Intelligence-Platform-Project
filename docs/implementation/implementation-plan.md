# Implementation Plan

Execution: autonomous within a milestone, **approval-gated between milestones** (`CLAUDE.md` §7).
Each milestone lands on its own branch(es) and merges to `main` via PR after the milestone report is approved.

| Milestone | Scope | Requirements | Exit criteria |
|-----------|-------|--------------|---------------|
| **M0 Assessment & foundation** | Reconnaissance, requirements, RTM, ADRs, backend/frontend scaffolds, tooling, CI, baseline tests | IR-01, IR-02, IR-04, IR-05 (liveness) | Docs exist; all local checks green; CI workflow present |
| **M1 Runnable vertical slice** | Docker Compose (Postgres+pgvector), SQLAlchemy models + first Alembic migration, arXiv import by ID, PDF extraction, chunking (ADR-0003), MiniLM embeddings, persisted dense search API, minimal search UI, readiness endpoint, JSON logging, background job runner | FR-01 (by ID), FR-02, FR-04–FR-08, FR-17 (states), IR-03, IR-05, IR-06, IR-08 | `docker compose up` → import one arXiv paper → search returns cited passages with pages; DB integration tests pass (locally or in CI service container) |
| **M2 Grounded Q&A** | Provider interface + Ollama adapter, prompt v1, JSON answer schema, citation resolver, abstention, query/answer persistence, Q&A UI with citation inspector | FR-09–FR-11, FR-18 (persist), IR-07, NFR-06, NFR-16 | Fake-provider tests for all error paths; ≥1 real-Ollama integration test; invalid citations never rendered valid |
| **M3 Evaluation & regression gates** | `eval/` dataset schema + manually labeled questions (team labels), Recall@k, MRR, citation validity, abstention, latency benchmark, run records, CI gate | FR-19–FR-21, NFR-01–NFR-04, NFR-07 | Baseline report with real numbers; CI gate active |
| **(Protocol step 4)** | Dedicated RAG evaluation audit | — | Separate audit report |
| **M4 Ingestion & corpus management** | PDF upload with validation, arXiv search UI, job retries, corpus browser/filters, paper details, delete, history UI, dashboard, settings view | FR-01, FR-03, FR-16, FR-17, FR-18, FR-22, FR-23 | Both ingestion paths E2E; upload security tests |
| **(Protocol step 5a)** | Security & privacy audit (first pass) | NFR-10, NFR-11 | Separate audit report |
| **M5 Summaries & extraction** | Single/cross-paper summaries, structured extraction, comparison, groundedness evaluation | FR-12–FR-15, FR-20 | Schema-validated outputs with evidence links; eval extensions |
| **M6 Retrieval optimization** | Hybrid BM25 + dense, optional reranker, small-to-big chunking experiment | FR-24, FR-25 | Controlled experiments on fixed eval set; trade-off report |
| **(Protocol step 6)** | CI/CD & reproducibility audit | NFR-08, NFR-14 | Separate audit report |
| **M7 Release readiness** | E2E tests, perf profiling, pilot uptime measurement, docs + handover; security audit second pass (step 5b) | NFR-03, NFR-05, IR-09 | Final acceptance (protocol step 7) |

## Open decisions needing team input

1. ~~Approve ADR-0003~~ — approved 2026-10-08.
2. ~~Install Docker Desktop~~ — done 2026-10-08; `docker compose up` verified.
3. Choose the eval-corpus domain (proposal suggests NLP) and who labels questions (M3; labels must be human).
4. Whether to amend the course proposal for ADR-0001 (Gemini → Ollama).

## Status

- M0 done (PR #2) · M1 done (PRs #3, #4) · M2 done, pending merge (`feature/m2-grounded-qa`).
