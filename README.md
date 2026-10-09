# UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project

**Scientific Literature Intelligence Platform:** a local, retrieval-augmented research assistant for scientific
papers. UCS503P (2026–27), Thapar Institute of Engineering and Technology. Authors: Paarth Ganesh, Diya Jain. Lab
instructor: Ms. Paramveer Kaur.

Import papers from arXiv or upload PDFs. The assistant extracts text page by page, indexes it with local
embeddings, and answers questions with a **local** Ollama model. Every claim cites the exact passage and page it
came from; citations are checked on the server; and when the papers don't support an answer, it says so instead
of guessing. No document or question leaves the machine (apart from arXiv downloads).

**MVP status (2026-10-09): MVP READY WITH DOCUMENTED LIMITATIONS.** See `docs/release/mvp-acceptance-report.md`
and `docs/release/mvp-known-limitations.md`.

## Implemented functionality

| Area | What works (requirement IDs in `docs/release/mvp-requirements-matrix.md`) |
|------|--------------------------------------------------------------------------------|
| Ingestion | arXiv search and import by ID (idempotent), PDF upload with validation, job tracking and retry (FR-01–FR-03, FR-17) |
| Processing | Page-aware PyMuPDF extraction, 256-token chunks with page and character provenance, MiniLM 384-dim embeddings in PostgreSQL + pgvector (FR-04–FR-07) |
| Search | Dense, BM25 and hybrid retrieval with cross-encoder reranking (FR-08, FR-24, FR-25) |
| Grounded Q&A | Local Ollama (`qwen2.5:3b`), citation chips with a source inspector, explicit "insufficient evidence" (FR-09–FR-11) |
| Analysis | Paper summary, cross-paper synthesis, structured extraction, comparison table (FR-12–FR-15) |
| Corpus | Browse, filter, details, delete; question history; dashboard; settings (FR-16, FR-18, FR-22, FR-23) |
| Evaluation | Recall@k / MRR harness, Q&A metrics, CI retrieval gate (FR-19–FR-21) |

**Measured** (`docs/evaluation/rag-evaluation-report.md`): Recall@5 0.875 (target 0.80; 50 assistant-written,
unreviewed labels), citation validity 1.00, 9/10 unanswerable questions abstained, warm Q&A p95 4.4–4.5 s (target
3 s **not met**).

## Documentation

| Topic | Document |
|-------|----------|
| Architecture and data-flow diagrams | `docs/architecture/overview.md`, `docs/architecture/data-model.md` |
| Step-by-step setup, tests, demo | `docs/operations/mvp-setup-and-testing.md` |
| Operations (config, backup, troubleshooting) | `docs/operations.md` |
| Acceptance, requirements status, limitations | `docs/release/` |
| Evaluation method and results | `docs/evaluation.md`, `docs/evaluation/` |
| Security | `docs/security.md`, `docs/security/` |
| Decisions | `docs/adr/` |
| History of the work | `docs/implementation/progress.md` |
| Handover | `docs/handover.md` |
| Project report (LaTeX, TIET class, five UML diagrams) | `report/` (build: `report/README.md`) |

## Layout

| Path | Contents |
|------|----------|
| `backend/` | FastAPI service (Python 3.12, uv), Alembic migrations |
| `frontend/` | React + TypeScript + Vite app |
| `docker-compose.yml` | PostgreSQL + pgvector, backend, frontend (localhost-only ports) |
| `docs/` | Requirements, architecture, ADRs, plan, progress, evaluation, security, operations, handover, audits |
| `eval/` | Evaluation corpus manifest, question set, run records, uptime logs |
| `scripts/` | Operational scripts (availability probe) |
| `Project Proposal/` | Submitted course proposal |
| `CLAUDE.md` | Engineering contract |

## Prerequisites

- Docker Desktop (WSL2 backend on Windows)
- [Ollama](https://ollama.com/) running on the host, then `ollama pull qwen2.5:3b` (~2 GB). Q&A and analyses need
  it; search works without it. The backend reaches it at `host.docker.internal:11434` (Docker) or
  `127.0.0.1:11434` (local). Change the model with `SLIP_OLLAMA_MODEL`; the model is recorded with every answer.
- For local development without containers: [uv](https://docs.astral.sh/uv/) and Node.js 24

## Run the full stack (Docker Compose)

1. Copy `.env.example` to `.env` in the repo root and set `POSTGRES_PASSWORD`.
2. Start everything:

```bash
docker compose up --build
```

3. Open http://localhost:8080. API docs: http://localhost:8000/api/v1/docs.

The first start downloads the embedding model and the reranker (~90 MB each) into the `hf-cache` volume (about
15 minutes on the reference network); `/api/v1/ready` reports `loading` for `embedding_model` / `reranker` until
both are ready. Ports bind to 127.0.0.1 only. Full step-by-step guide and test matrix:
`docs/operations/mvp-setup-and-testing.md`.

Database migrations run automatically when the backend container starts (`alembic upgrade head`). Run them by
hand for local development (below) or for the evaluation database.

## Demonstration

With `/api/v1/ready` all green:

1. Import arXiv `1706.03762v7`.
2. Search for a concept.
3. Ask "What BLEU score does the big Transformer model achieve on the WMT 2014 English-to-German translation
   task?" and open citation **P1**.
4. Ask something the paper does not cover, to see *insufficient evidence*.
5. Summarise or extract a paper, and compare two.

The full script is in `docs/release/mvp-acceptance-report.md` §7.

## Local development

Database only, in Docker:

```bash
docker compose up -d db
```

Backend (http://localhost:8000). Create `backend/.env` from `.env.example` first (set `SLIP_DATABASE_URL`):

```bash
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```

Frontend (http://localhost:5173, proxies `/api` to the backend):

```bash
cd frontend && npm install && npm run dev
```

## Checks

Backend unit tests, lint, types:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -m "not integration and not model and not network and not ollama and not e2e"
```

Backend integration tests (need the `slip_test` database the compose `db` service creates, and `SLIP_TEST_DATABASE_URL`):

```bash
cd backend && uv run pytest -m "integration or model"
```

Real local model checks (manual; needs Ollama with `qwen2.5:3b`):

```bash
cd backend && uv run pytest -m ollama
```

Live arXiv check (manual, network):

```bash
cd backend && uv run pytest -m network
```

End-to-end against the running Docker stack (manual; needs Ollama; uploads and then deletes a synthetic paper):

```bash
cd backend && SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 uv run pytest -m e2e
```

Frontend:

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Evaluation

Uses a separate database (`slip_eval`) built from the pinned corpus in `eval/corpus.json`. Labels in
`eval/qa_v1.json` were written by the AI assistant and are not human-reviewed (ADR-0007).

```bash
docker compose exec db psql -U slip -d slip -c "CREATE DATABASE slip_eval OWNER slip"
```

Then, with `SLIP_DATABASE_URL` pointing at `slip_eval` (use `127.0.0.1`):

```bash
cd backend && uv run alembic upgrade head && uv run python -m app.evaluation build-corpus && uv run python -m app.evaluation check-labels && uv run python -m app.evaluation retrieval
```

`python -m app.evaluation qa` runs grounded Q&A over all items (needs Ollama). Each run writes a record to
`eval/runs/`. Plug the laptop in for latency measurements: battery power roughly doubles Q&A latency.

## Troubleshooting

- `uv` errors about hardlinks inside OneDrive: the project sets `link-mode = "copy"` in `backend/pyproject.toml`.
- `/api/v1/ready` returns 503 with `database: unreachable or not migrated`: start `db` and run `alembic upgrade head`.
- Search returns 503 "pgvector X is installed; 0.8.0 or newer is required": use the compose `db` service
  (pgvector 0.8.0) or upgrade the extension.
- Database connections take ~15 s each on Windows: use `127.0.0.1`, not `localhost`, in `SLIP_DATABASE_URL`.
  `localhost` resolves to IPv6 `::1` first, and Docker publishes PostgreSQL on `127.0.0.1` only.
- Docker build fails with `invalid file request <path>`: OneDrive cloud placeholders. Move the repository
  out of OneDrive (recommended), or build from a copy outside it.
- Q&A returns 503 "Ollama is not reachable": start Ollama. 503 "not installed": `ollama pull qwen2.5:3b`.
- An import fails with "Interrupted by a server restart": the backend restarted mid-job; import the paper again.
- Search returns 503 "Reranker model … could not be loaded": the first start needs internet access to download
  `cross-encoder/ms-marco-MiniLM-L-6-v2`, or set `SLIP_SEARCH_MODE=hybrid` (no reranker).
- Searches take ~2 s: expected in the default `hybrid_rerank` mode on CPU (`docs/evaluation.md` §7).
