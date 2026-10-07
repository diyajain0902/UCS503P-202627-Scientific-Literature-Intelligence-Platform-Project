# Progress Log

Newest first. Record facts only: what changed, commands run, actual results.

## 2026-10-08 — Milestone 1: Runnable vertical slice (branch `feature/m1-vertical-slice`)

**Approvals received:** M1 scope; ADR-0003 (256-token window, 38 overlap); team to install Docker.

**M0 re-validation:** PR #2 merged; CI green on the PR and on `main` → IR-04 verified.

**Delivered:** arXiv import by ID (allow-listed HTTPS hosts, rate-limited, size-capped, defusedxml);
PyMuPDF page-aware extraction with rejection of non-PDF/corrupt/encrypted/oversized/text-less PDFs;
deterministic token-window chunking on the MiniLM tokenizer; MiniLM embeddings with dimension and
input-length validation; PostgreSQL + pgvector schema (migration `0001`, HNSW cosine index, constraints);
in-process job runner (ADR-0005); `/papers/arxiv`, `/jobs/{id}`, `/papers`, `/papers/{id}`, `/search`, `/ready`;
error envelope; JSON logs with request IDs; React UI (status bar, import with live job state, corpus list,
search results with pages, scores, arXiv links); Docker Compose (localhost-only ports) and Dockerfiles;
CI jobs for integration tests (pgvector service + real model) and image builds.

**Environment facts found:** uv must use `link-mode = "copy"` inside OneDrive (hardlinks rejected, os error 396).
First MiniLM download + load took 272.8 s on this network; encode of 64 short sentences on CPU: 0.16 s.
Verified `max_seq_length = 256`, dimension 384, vectors L2-normalized.

**Commands and results (local, Windows, Python 3.12.13):**
- `uv run ruff check .` / `ruff format --check .` → pass. `uv run mypy` (strict) → no issues in 45 files.
- `uv run pytest -m "not integration and not model and not network"` → **75 passed**.
  First run had 2 failures caused by a wrong test case (`1706.0376` is a valid pre-2015 ID format); test fixed.
- `uv run pytest -m "model or network"` → **5 passed** (real MiniLM; live arXiv fetch of 1706.03762v1 + extraction).
- `uv run pytest` without `SLIP_TEST_DATABASE_URL` → 28 integration tests **skipped** locally (no Docker).
- Frontend: `lint`, `typecheck`, `build` pass; `npm test` → **10 passed** (4 files).

**CI (GitHub Actions run 37683723123, commit 903339d):** `frontend`, `backend`, `backend-integration`
(28 integration + 4 model tests against `pgvector/pgvector:0.8.0-pg17`), `docker-images` (compose config +
build) → all **success**. Per-test counts in CI logs were not retrieved (log download requires authentication);
job success means pytest exited 0 and the DB URL was set, so no integration test could skip.

**Not verified:** `docker compose up` end-to-end on the reference machine; real-model ingestion of a real arXiv
PDF through the full pipeline into PostgreSQL (each half verified separately); search latency; retrieval quality.

## 2026-10-08 — Milestone 0: Assessment and foundation

**Baseline (before changes):** repository contained only `README.md` (title line), `CLAUDE.md`, and
`Project Proposal/` (`main.tex`, `main.pdf`). No code, manifests, tests, CI, or schema. Nothing to build or test.

**Environment discovered:**
- Windows 11 Home 10.0.26200; Ryzen 7 7435HS (16 threads); 15.8 GB RAM; NVIDIA RTX 3050 Laptop 4 GB; ~119 GB free on C:.
- Python 3.14.5 (system), uv 0.11.7, Node 24.16.0, npm 11.13.0, Ollama 0.34.4 (server running on `localhost:11434`).
- Ollama models installed: `qwen2.5:3b` (Q4_K_M), `nomic-embed-text` (not used — contract mandates MiniLM).
- Missing: Docker, `psql`, GitHub CLI, WSL.

**Ollama probe (manual, not an automated test):** two `/api/generate` calls to `qwen2.5:3b` with `format: json`,
`temperature: 0`, `num_predict: 64`. Both returned valid JSON with correct answers. Cold: total 10.04 s
(load 9.69 s). Warm: total 0.24 s, 10 tokens in 0.14 s. Loaded size 2.16 GB, fully in VRAM; default context 4096.

**Changes:**
- `uv python install 3.12` → CPython 3.12.13 (managed by uv).
- Backend scaffold: `backend/` with FastAPI app factory, `/api/v1/health`, versioned OpenAPI, CORS allow-list,
  `pydantic-settings` config; Ruff, mypy strict, Pytest configured; `uv.lock` committed.
- Frontend scaffold: Vite React-TS template, boilerplate removed, health-status shell with loading/error states,
  Vitest + Testing Library + jsdom, `typecheck` and `test` scripts, `strict` TypeScript, dev proxy `/api → :8000`.
- CI: `.github/workflows/ci.yml` (backend + frontend jobs).
- Repo hygiene: `.gitignore` (secrets, data, model artifacts), `.gitattributes`, `.env.example`.
- Docs: requirements (FR/NFR/AC/RTM), architecture overview + data model, ADR-0001…0004, this plan and log.
- `CLAUDE.md`: §8 doc paths updated; §1 requirement table replaced by a pointer to the canonical register (the Step 1 table used a different FR numbering — two schemes would break traceability; no code referenced the old IDs); frontend linter corrected to oxlint; ADR-0001 referenced.

**Commands and results:**
- `uv run ruff check .` → All checks passed. `uv run ruff format --check .` → 10 files already formatted.
- `uv run mypy` → Success: no issues found in 10 source files (after fixing 1 lint + 1 type error found on first run).
- `uv run pytest -q` → 7 passed, 1 warning (Starlette deprecation: `httpx` with `starlette.testclient`; third-party, not suppressed).
- `npm run lint` → clean. `npm run typecheck` → clean. `npm test` → 2 passed. `npm run build` → built (220 kB JS, 69 kB gzip).

**Not done / blocked:** CI not yet observed running on GitHub (runs on PR). Docker missing (blocks M1 DB work locally).
