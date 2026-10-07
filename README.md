# UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project

UCS503P 202627 Scientific Literature Intelligence Platform Project — a retrieval-augmented research assistant that
answers questions over arXiv and uploaded papers with citations to source pages. Everything runs locally
(sentence-transformers embeddings, PostgreSQL + pgvector, Ollama for generation).

**Status:** Milestone 0 (foundation). Only the health endpoint and app shell exist; ingestion, search, and Q&A are not implemented yet.

## Layout

| Path | Contents |
|------|----------|
| `backend/` | FastAPI service (Python 3.12, uv) |
| `frontend/` | React + TypeScript + Vite app |
| `docs/` | Requirements, architecture, ADRs, plan, progress |
| `Project Proposal/` | Submitted course proposal |
| `CLAUDE.md` | Engineering contract |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (installs Python 3.12 automatically)
- Node.js 24 + npm
- [Ollama](https://ollama.com/) with `ollama pull qwen2.5:3b` (needed from Milestone 2)
- Docker Desktop (needed from Milestone 1 for PostgreSQL + pgvector)

## Run locally

Backend (http://localhost:8000, docs at `/api/v1/docs`):

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload
```

Frontend (http://localhost:5173, proxies `/api` to the backend):

```bash
cd frontend && npm install && npm run dev
```

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npm run build
```

Configuration: copy `.env.example` to `backend/.env`. See `docs/` for requirements and architecture.
