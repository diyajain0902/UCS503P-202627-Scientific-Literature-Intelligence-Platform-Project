# Progress Log

Newest first. Record facts only: what changed, commands run, actual results.

## 2026-10-08 — Milestone 3: Evaluation and regression gates (branch `feature/m3-evaluation`)

**Approval:** M3; domain NLP; **the team instructed the AI assistant to write all labels** (ADR-0007; `CLAUDE.md`
§5 updated). All items carry `labeler: ai-assistant`, `review_status: unreviewed`. No human review has happened.

**Delivered:** `backend/app/evaluation/` (dataset schema, metrics, corpus builder/verifier, label checker, runners,
CLI `python -m app.evaluation`); `eval/corpus.json` (20 NLP papers pinned to exact arXiv versions);
`eval/qa_v1.json` (40 answerable, 10 unanswerable, 110 evidence quotes); run records in `eval/runs/`;
CI job `retrieval-eval`; `docs/evaluation.md`; ADR-0007.

**Corpus build:** 20/20 papers ingested into `slip_eval` (1,207 pages, 1,634 chunks); manifest verified.

**Labelling method:** evidence located by keyword search of each paper's extracted text (not the retriever);
questions paraphrased; every quote verified by `check-labels`. Unanswerable items checked for absence of the
answer by corpus-wide keyword search (notes per item); several are adversarial (name a corpus paper, ask for a fact
only a neighbouring paper has).

**Label-completeness review (found and fixed):** the first labels gave Recall@5 = 0.50, but all 20 misses had the
correct paper in the top 5. A retriever-independent keyword review of every answerable item's gold paper raised
the quotes from 52 to 110 and found two **wrong labels**: q026's quote described DPR's reader, not its encoders;
q019's generic quote also matched prior-work passages. Both corrected. The pre-review run record is kept.

**Defects found in the tooling and fixed:** (1) Q&A latency included cold model loading for the first question
(33-41 s) and was labelled "warm"; the runner now warms both models first and measures cold start separately by
unloading the model; the two mislabelled Q&A records were deleted before commit. (2) Latency varied 2-3x between
runs because the laptop switched to battery; run records now include `power_source`. (3) Run records were written
with CRLF; now LF.

**Baselines** (details and tables: `docs/evaluation.md` §6):
- Retrieval, official record `eval/runs/20261008T170309Z_retrieval_3eab94d.json` (clean commit, battery):
  Recall@1 0.200, **Recall@5 0.700**, Recall@10 0.775, MRR 0.416, search p50/p95 41/50 ms. NFR-01 (0.80) not met.
  Reproduced exactly from the earlier run (deterministic).
- Q&A at qa_min_score 0.30: answer rate 0.75-0.825, cited-relevant 0.525-0.55, abstention recall 1.00,
  false answers 0/10, citation validity 1.00 (records `20261008T135804Z_qa_03a01de.json`,
  `20261008T164846Z_qa_03a01de.json`). Warm p50/p95 1.29/2.74 s (plugged in, likely) and 3.30/7.24 s
  (battery); cold start 5.9-10.5 s. Run-to-run variance is material.
- qa_min_score 0.40 run (`20261008T164357Z_qa_03a01de.json`): no quality change beyond variance; its latency is
  invalid (run spanned about 3 h, probable sleep). Default kept at 0.30 (tuning on the test set avoided).

**CI gate:** Recall@5 >= 0.675 (baseline minus one item for cross-platform float differences).

**Commands and results (local):** ruff, format, mypy strict (64 files) pass; unit **116 passed**;
`pytest -m "integration or model"` **51 passed**; `check-labels` ok; retrieval gate passed locally.

## 2026-10-08 — Milestone 2: Grounded Q&A (branch `feature/m2-grounded-qa`)

**Approval:** M2, with the constraint "keep qwen2.5:3b" (no other models downloaded or compared).

**Delivered:** generation provider interface + Ollama adapter (bounded options, warm-up, error mapping);
prompt `qa-v1` with delimited, neutralised evidence and `P1..Pn` labels; constrained JSON schema; citation checker;
three-point abstention; `POST /api/v1/qa`, `GET /api/v1/qa`, `GET /api/v1/qa/{id}`; migration `0002`
(`queries`, `answers`, `answer_evidence`, `answer_citations`); Q&A page with citation chips, inspector,
invalid/unsupported flags, insufficient-evidence notice; Ask / Search tabs. ADR-0006.

**Defects found and fixed during M2:**
1. Real-model test: the first prompt made qwen2.5:3b abstain on clearly answerable questions (0-1/4 on a synthetic
   set). Cause: a trailing JSON-format hint line in the prompt. Removed; rules rewritten answer-first.
2. Real paper passages: the model wrote labels and math fragments into claim text and looped to the 512-token
   limit (HTTP 502); another claim's text was just `P1`. Fixed by schema order (citations before text), a label
   pattern, a 300-character claim cap, and a server guard that drops label-only claims.
3. A worked example in the prompt raised recall (5/6) but produced a cited, invented answer to an unanswerable
   question; rejected (see ADR-0006 table).
4. Persistence: citations were inserted before their evidence rows (FK violation), and empty collections were
   lazy-loaded after the session closed. Fixed with an explicit relationship and assigned collections. Test DB
   cleanup now truncates the Q&A tables.
5. A shell heredoc wrote literal backspace bytes into a regex (`\b` became 0x08), silently disabling the
   label-only guard. Caught by a manual spot check; file rewritten; repo scanned (no other occurrences);
   regression test added.

**Environment issue:** Docker builds failed with `invalid file request` because OneDrive keeps cloud reparse
points on older files even when pinned (`attrib +P` was applied to the project and did not help). Verification
used a `robocopy` of the working tree in `%TEMP%\slip-build` (same Compose project and volumes). Recommended fix:
move the repository outside OneDrive (team decision).

**Commands and results (local):**
- Ruff, format, mypy strict (56 files) -> pass.
- Unit: `pytest -m "not integration and not model and not network and not ollama"` -> **103 passed**.
- Integration (Compose PostgreSQL 17 + pgvector 0.8.0): `pytest -m integration` -> **43 passed** (incl. 13 Q&A
  tests and the `alembic check` drift test with migration 0002).
- Real model: `pytest -m ollama` -> **3 passed** (answerable -> answered with a valid citation; unanswerable ->
  abstains; instruction inside a passage not followed).
- Frontend: lint, typecheck, build pass; `npm test` -> **13 passed** (5 files).

**Real end-to-end smoke run** (Docker stack via nginx; corpus = 1706.03762v7 only; qwen2.5:3b warm, temperature 0,
seed 0, num_ctx 4096; 8 questions written by the developer; not a labelled evaluation):
- 5/6 answerable questions answered with valid citations: BLEU 28.4 (p. 8); scaling by 1/sqrt(d_k) (p. 4);
  d_model 512 (p. 8, terse claim "dmodel 512"); 100,000 steps / 12 hours (p. 7); attention heads: cited p. 8, but
  the claim describes varying the number of heads rather than stating 8 (valid citation, claim does not answer).
- 1/6 abstained (optimizer). Verified retrieval miss: the passage containing "Adam" is not in the top 6.
- 2/2 unanswerable questions abstained. No invented answers, no truncation.
- Server-side latency 701-1686 ms per question (8 samples, model warm). Not a p95 measurement.
- Browser: the Q&A page answered "How long was the base model trained?" with chip P1; the inspector showed the
  p. 7 passage.

## 2026-10-08 — Milestone 1 closure: Docker verification on the reference machine

**Setup by the team:** WSL 3.0.1 (manual MSI after `wsl --install` returned HTTP 403), VirtualMachinePlatform
feature enabled, Docker Desktop 29.8.2 (per-user install). Root `.env` created locally with a random password
(git-ignored).

**`docker compose up -d --build`:** all three services up; `db` and `backend` healthy. First build >10 min (CPU
PyTorch layer); later starts reuse the cache.

**End-to-end through the frontend's nginx proxy (`http://localhost:8080/api/v1`):**
- `/ready` → ready: `pgvector 0.8.0, schema revision 0001`; MiniLM loaded (384-dim); Ollama `qwen2.5:3b`
  reachable from the container via `host.docker.internal`.
- Import `1706.03762v7` → `ready` in 5 s.
- Search "why use multi-head attention instead of a single attention function" (top_k 3) → 39.4 ms; top hit is
  the multi-head attention passage, pp. 4–5 (score 0.552). Single manual query, not an evaluation.
- Browser UI at `http://localhost:8080`: status bar green for all three dependencies; query "positional encoding
  sine cosine" → top passage is the sinusoidal positional-encoding text, p. 6.

**Tests against the Compose database (pgvector 0.8.0):** `pytest -m "integration or model"` → **32 passed**
(154 s); unit suite → **85 passed**; ruff and mypy clean.

**Defect found and fixed:** on this Windows machine `localhost` resolves to `::1` first; Docker publishes
PostgreSQL on `127.0.0.1` only, so every new DB connection took ~15–17 s (measured: `127.0.0.1` 2.1 s vs
`localhost` 17.1 s including interpreter start-up). The test suite appeared hung. Defaults in `config.py`,
`.env.example`, and CI now use `127.0.0.1`; README troubleshooting updated.

**M1 open items now closed:** `docker compose up` (IR-03) and search on pgvector ≥ 0.8.0 locally.

## 2026-10-08 — Milestone 1 addendum: local database verification and pgvector defect

**Docker:** not installed. Installing Docker Desktop requires enabling WSL2/Hyper-V (Windows system features,
administrator rights, reboot) and accepting Docker's licence; left to the team.

**Workaround used (no system changes):** `pgserver` (PyPI) in a throwaway venv under `%TEMP%\slippg`, providing
PostgreSQL 16.2 with **pgvector 0.6.2** on `localhost:5433` (trust auth, localhost only). Stopped afterwards.

**Defect found and fixed:** pgvector < 0.8.0 rejects `hnsw.iterative_scan` ("reserved prefix"), so every search
returned an unexplained HTTP 500. Fix: `app/retrieval/search.py` checks the installed pgvector version; search returns
HTTP 503 `dependency_unavailable` ("pgvector 0.6.2 is installed; 0.8.0 or newer is required") and `/ready` reports
the same. Regression tests: `tests/test_pgvector_version.py` (10 tests). Docker Compose and CI pin 0.8.0.

**Local results against PostgreSQL 16.2 + pgvector 0.6.2:**
- `pytest -m integration` → **24 passed, 4 failed**. The 4 failures are the search/readiness tests, failing with
  the new explicit 503 because 0.6.2 is below the minimum — expected; they pass on 0.8.0 in CI.
- Unit suite → **85 passed**. Ruff, mypy strict → pass.

**Real end-to-end ingestion (first time with every real component):** backend via `uvicorn`, `POST /papers/arxiv`
`1706.03762v7` → job `ready` after 75 s (includes rate-limit wait and MiniLM load). Stored: title "Attention Is All
You Need", 15 pages, 45 chunks, token counts 244–254, all vectors 384-dim, 15 chunks spanning two pages,
chunker `tokwin-v1|sentence-transformers/all-MiniLM-L6-v2|w256|o38`, extractor `pymupdf-1.28.2/v1`.
Logs contained event names, IDs, and sizes only. Search on this database correctly returned the 503 above.

**Still not verified locally:** search on pgvector ≥ 0.8.0 (verified in CI only); `docker compose up`.

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
