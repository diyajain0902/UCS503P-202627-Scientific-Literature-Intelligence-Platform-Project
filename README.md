# UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project

UCS503P 202627 Scientific Literature Intelligence Platform Project — a retrieval-augmented research assistant that
answers questions over arXiv and uploaded papers with citations to source pages. Everything runs locally
(sentence-transformers embeddings, PostgreSQL + pgvector, Ollama for generation).

**Status:** Milestone 1 (vertical slice). Working: arXiv import by ID → page-aware extraction → chunking →
local embeddings → pgvector semantic search, with a web UI. Not yet: grounded Q&A (M2), evaluation (M3),
PDF upload and corpus management (M4).

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
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -m "not integration and not model and not network"
```

Backend integration tests (need the `slip_test` database the compose `db` service creates, and `SLIP_TEST_DATABASE_URL`):

```bash
cd backend && uv run pytest -m "integration or model"
```

Live arXiv check (manual, network):

```bash
cd backend && uv run pytest -m network
```

Frontend:

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

## Troubleshooting

- `uv` errors about hardlinks inside OneDrive: the project sets `link-mode = "copy"` in `backend/pyproject.toml`.
- `/api/v1/ready` returns 503 with `database: unreachable or not migrated`: start `db` and run `alembic upgrade head`.
- Search returns 503 "pgvector X is installed; 0.8.0 or newer is required": use the compose `db` service
  (pgvector 0.8.0) or upgrade the extension.
- An import fails with "Interrupted by a server restart": the backend restarted mid-job; import the paper again.
