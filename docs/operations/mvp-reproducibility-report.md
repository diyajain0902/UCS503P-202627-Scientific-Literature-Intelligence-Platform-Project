# MVP CI/CD and Reproducibility Report

- **Date:** 2026-10-09. **Branch:** `chore/mvp-reproducibility-check` from `main` at `4d31e7b` (step 5b merged).
- **Machine:** Windows 11, Ryzen 7 7435HS, 16 GB RAM, RTX 3050 4 GB, Docker Desktop (WSL2), Ollama with
  `qwen2.5:3b`.
- **Method:** a fresh `git clone` into `%TEMP%\slip-clean`, **outside OneDrive**. I followed the README with a new
  `.env` (random password) under a separate Compose project, `slipclean`, with new volumes. The existing stack was
  stopped (not removed) while the clean one used the ports, then restarted with its data intact. The clean
  project's own throwaway volumes were deleted at the end.

## 1. Setup verification

| Item | Result |
|------|--------|
| `.env.example` | Complete for Compose and local runs; no real secrets. Copying it and setting `POSTGRES_PASSWORD` was enough. **No change needed** |
| Backend dependencies (`uv sync --locked`, fresh venv) | Pass, 280 s (packages partly from the uv cache) |
| Frontend dependencies (`npm ci`) | Pass, 23 s, 0 vulnerabilities |
| `docker compose up -d --build` | Pass. **Note:** 45 s because Docker reused image layers built earlier on this machine, so this was *not* a cold image build (M1 measured a cold build at > 10 min) |
| Database initialisation | A fresh volume was migrated `0001 → 0006` by the backend's start command; `/ready` reported "schema revision 0006". `slip_test` was created by `docker/db-init` |
| PostgreSQL / pgvector | `pgvector 0.8.0` reported by `/ready` |
| Ollama | Host Ollama reachable from the container via `host.docker.internal`; `qwen2.5:3b` available |
| Time to fully ready on fresh volumes | **About 15 minutes**, almost all Hugging Face downloads into the new `hf-cache` volume (the embedding model loaded after 14.7 min) |
| Startup and shutdown commands | As documented (`up -d --build`, `down`) |

## 2. Quality checks executed (fresh clone unless noted)

| Check | Result |
|-------|--------|
| `ruff check`, `ruff format --check`, `mypy` strict | Pass (78 source files) |
| Backend unit (mocked embedder/LLM/arXiv) | **139 passed** (after the fixes below; 137 before them) |
| Integration + real MiniLM (`integration or model`, clean DB, `SLIP_REQUIRE_TEST_DATABASE=1`) | **83 passed**, 0 skipped. Includes `alembic check` drift and the downgrade/upgrade round trip |
| Real Ollama (`pytest -m ollama`) | **3 passed** (answers with a valid citation, abstains, ignores injected instructions) |
| End-to-end on the clean stack (`pytest -m e2e`) | **7 passed** (ready; upload → ingest; search in 4 modes; Q&A citation validity; summary; delete) |
| Frontend lint, typecheck, Vitest, production build | Pass; **24 passed**; build OK |
| Docker images | Built (cached layers, see above) |

## 3. Core journey on the clean stack (manual, real components)

| Step | Result |
|------|--------|
| Import `1706.03762v7` from arXiv | `ready` in 11 s |
| Search "why scale dot-product attention by the square root of d_k" | Page-4 passages ranked first. **First search took 87 s**: the reranker had failed to download at start-up and loaded on first use (finding R-2) |
| Q&A: BLEU of the big Transformer on WMT14 EN-DE | **Answered**; citation P1 valid → chunk on page 8 containing "28.4"; latency 5.7 s |
| Q&A: scaling by 1/√d_k | Insufficient evidence: the answering passage was P1 and the model abstained anyway (model behaviour) |
| Q&A: training time and hardware | Insufficient evidence: the answering chunk (page 7) was not in the top 6 (retrieval miss) |
| Citation resolution | For both answers, all evidence snapshots matched their stored chunks: 5/5 and 6/6 text and pages (SQL) |
| Citation inspection in the UI | History → saved answer → chip P1 opens "[P1] Attention Is All You Need · arXiv:1706.03762v7 · p. 8"; no console errors |
| Database stopped | `/ready` 503 with a clear reason. **Search/list returned a generic 500** (finding R-3); after the fix, 503 "The database is unavailable…" (verified) |
| Ollama unreachable (one-off container) | `/ready` shows `ollama: unreachable (ConnectError)`; search 200; Q&A 503 "Ollama is not reachable…; start Ollama to use Q&A" |

## 4. CI status

| Run | Result |
|-----|--------|
| `main` @ `9adc518` (M7 merge) | All 6 jobs passed |
| `main` @ `1ab4a0b` (step 4 merge) | **Failed:** `retrieval-eval → build-corpus`. Annotations: arXiv HTTP 429 / timeouts for 10 of 20 papers (finding R-1) |
| `main` @ `4d31e7b` (step 5b merge) | 5 jobs passed; `retrieval-eval` still running when last checked. The final result was not observed (GitHub API rate limit) |
| This branch | Pushed; result to be checked on GitHub |

**Silent-pass review:**
- Every CI step is a plain `run:` with no `|| true`, `continue-on-error` or `set +e`.
- pytest, the retrieval gate (`--min-recall-at-5` exits non-zero) and Vitest all fail the step on failure.
- One gap: integration tests *skip* when `SLIP_TEST_DATABASE_URL` is missing, which would turn the job green
  without testing anything (finding R-4, fixed).
- CI never contacts Ollama: `ollama` and `e2e` tests are excluded or skipped.

## 5. Findings and fixes

| ID | Severity | Finding | Fix | Verification |
|----|----------|---------|-----|--------------|
| R-1 | High (CI) | `retrieval-eval` fails when arXiv rate-limits the runner | `build-corpus` retries only failed papers after 30 / 90 / 180 s and reports the final attempt's failures; unused `job_failures` removed | `test_build_corpus_retries_rate_limited_papers`, `test_build_corpus_reports_papers_that_never_succeed` (pass). Not yet observed in CI |
| R-2 | Medium | `/ready` said "ready" while the reranker had failed to load; the first search then blocked on the download (87 s; nginx times out at 120 s) | `/ready` now includes `reranker` (ok if not used, loaded, or disabled; otherwise `loading` or the load error), required for "ready"; UI label added | `test_readiness_reports_reranker_state`; clean stack showed `reranker … loaded` |
| R-3 | Medium | Database outage gave a generic 500 | SQLAlchemy `OperationalError` → 503 `dependency_unavailable` with a fixed, actionable message | `test_database_outage_is_an_understandable_503`; live: 503 with the DB stopped, 200 after restart |
| R-4 | Medium (CI) | Missing test DB would make the integration job pass by skipping | `SLIP_REQUIRE_TEST_DATABASE=1` in CI turns the skip into a failure | Locally: with the flag and no DB → 13 errors; without it → 13 skipped |

## 6. Known environment limitations

- **OneDrive:** Docker builds from the OneDrive folder fail. Clone elsewhere (verified working from `%TEMP%`).
- **First start is slow:** model downloads took ~15 min on this network. A Hugging Face token (`HF_TOKEN`) raises
  rate limits but is optional and not configured.
- **A cold image build was not measured here** (layer cache present).
- **No GPU in containers:** embeddings and reranking run on CPU, so search in `hybrid_rerank` takes ~1–2 s.
- **Ollama runs on the host**, not in Compose, and must be started separately. On this machine it is exposed to
  the network (security finding SEC-01).
- **GitHub Actions** warn that Node 20 actions (`checkout@v4`, `setup-uv@v5`, `cache@v4`) are being forced onto
  Node 24. They still work; upgrading the action versions is optional.
- **Q&A is probabilistic:** expect some abstentions on answerable questions; choose demo questions in advance.

## 7. Reproducing the demonstration

Follow `mvp-setup-and-testing.md` §2–§3: clone outside OneDrive, `.env` from the example, `docker compose up -d
--build`, wait for `/ready` = ready (all four checks ok), import `1706.03762v7`, then ask the BLEU question and
open citation P1.
