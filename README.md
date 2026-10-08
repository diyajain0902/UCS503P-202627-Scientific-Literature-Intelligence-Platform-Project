# UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project

UCS503P 202627 Scientific Literature Intelligence Platform Project — a retrieval-augmented research assistant that
answers questions over arXiv and uploaded papers with citations to source pages. Everything runs locally
(sentence-transformers embeddings, PostgreSQL + pgvector, Ollama for generation).

**Status:** Milestone 3 (evaluation) complete. Baseline: Recall@5 0.70 (target 0.80 not met); see
`docs/evaluation.md`. Milestone 2: Working: arXiv import by ID → page-aware extraction → chunking → local embeddings →
pgvector semantic search, and grounded Q&A with the local Ollama model (citations checked server-side, explicit
"insufficient evidence"). Not yet: evaluation (M3), PDF upload and corpus management (M4), summaries (M5).

## Layout

| Path | Contents |
|------|----------|
| `backend/` | FastAPI service (Python 3.12, uv), Alembic migrations |
| `frontend/` | React + TypeScript + Vite app |
| `docker-compose.yml` | PostgreSQL + pgvector, backend, frontend (localhost-only ports) |
| `docs/` | Requirements, architecture, ADRs, plan, progress |
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

The first start downloads the embedding model (~90 MB) into the `hf-cache` volume; `/api/v1/ready` reports
`embedding_model: loading` until it finishes. Ports bind to 127.0.0.1 only.

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
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -m "not integration and not model and not network and not ollama"
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
