# UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project

UCS503P 202627 Scientific Literature Intelligence Platform Project — a retrieval-augmented research assistant that
answers questions over arXiv and uploaded papers with citations to source pages. Everything runs locally
(sentence-transformers embeddings, PostgreSQL + pgvector, Ollama for generation).

**Status (2026-10-09):** milestones M0–M6 merged; M7 (release readiness) delivered on
`feature/m7-release-readiness`, awaiting team approval. Working end to end: arXiv import and PDF upload →
page-aware extraction → chunking → local embeddings → hybrid search (dense + BM25 + cross-encoder rerank) → grounded
Q&A with the local Ollama model (server-checked citations, explicit "insufficient evidence"), summaries, synthesis,
extraction, comparison, corpus management, evaluation harness with a CI gate.
Measured (`docs/evaluation.md` §7): Recall@5 0.875 (target 0.80; assistant-written, unreviewed labels); Q&A warm p95
4.4–4.5 s (target 3 s **not met**). Handover: `docs/handover.md`. Operations: `docs/operations.md`.

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
- [Ollama](https://ollama.com/) with `ollama pull qwen2.5:3b` (used from Milestone 2; search works without it)
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
