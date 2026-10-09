# MVP Setup and Testing Guide

How to install, start, test and demonstrate the MVP from a fresh clone. These steps were followed exactly on
2026-10-09 (see `mvp-reproducibility-report.md`). Background and troubleshooting: `README.md`,
`docs/operations.md`.

## 1. Requirements

| Component | Version / note |
|-----------|----------------|
| Docker Desktop | WSL2 backend on Windows; Compose v2 |
| Ollama | Running on the host, with `ollama pull qwen2.5:3b` (~2 GB). Only Q&A and analyses need it; search works without it |
| Local development (optional) | `uv` (manages Python 3.12 itself) and Node.js 24 |
| Disk / network | First start downloads PyTorch (CPU) into the image, plus two models (~90 MB each) into the `hf-cache` volume |
| Location | **Clone outside OneDrive.** Docker builds inside OneDrive fail with `invalid file request` |

PostgreSQL 17 with pgvector 0.8.0 comes from the `pgvector/pgvector:0.8.0-pg17` image; nothing to install.

## 2. Start

```bash
git clone https://github.com/diyajain0902/UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project.git
cd UCS503P-202627-Scientific-Literature-Intelligence-Platform-Project
cp .env.example .env    # then set POSTGRES_PASSWORD to a random value; never commit .env
docker compose up -d --build
```

The backend applies all database migrations (`alembic upgrade head`) on every start.

Wait until `curl http://localhost:8080/api/v1/ready` returns `"status":"ready"`, with `database`,
`embedding_model`, `reranker` and `ollama` all `ok`. **On a fresh install this took about 15 minutes in the
reference run**, almost all of it model downloads. Don't start a demo until `reranker` is `ok`; otherwise the first
search waits for the download.

Open http://localhost:8080. Stop with `docker compose down`, which keeps the data. `docker compose down -v` deletes
**all** data.

## 3. Demo journey (verified)

1. **Add papers → Import by arXiv ID:** `1706.03762v7` reaches the job state `ready` (11 s in the reference run).
2. **Search passages:** "why scale dot-product attention by the square root of d_k" returns page-4 passages from
   *Attention Is All You Need*.
3. **Ask:** "What BLEU score does the big Transformer model achieve on the WMT 2014 English-to-German translation
   task?" is answered with a citation chip **P1**.
4. **Click P1:** the inspector shows the cited passage (arXiv 1706.03762v7, page 8, containing "28.4").
5. **History:** the saved answer reopens with the same evidence.

Expect some abstentions on answerable questions. In the reference run, 2 of 3 questions got "insufficient
evidence": one because the answering passage was not retrieved, one because the model abstained despite having
it (`docs/evaluation/known-failure-modes.md` FM-08). The system abstains rather than guess. Pick demo questions
in advance.

## 4. Tests

Run from `backend/` unless noted. Mocked components are marked in the test docstrings (fake embedder, scripted
fake LLM, fake arXiv).

| What | Command | Needs |
|------|---------|-------|
| Lint, format, types | `uv run ruff check . && uv run ruff format --check . && uv run mypy` | — |
| Unit (mocks) | `uv run pytest -m "not integration and not model and not network and not ollama and not e2e"` | — |
| Integration (real PostgreSQL + pgvector, real MiniLM; migration drift and round trip included) | `SLIP_TEST_DATABASE_URL=postgresql+psycopg://slip:<password>@127.0.0.1:5432/slip_test uv run pytest -m "integration or model"` | `db` running (it creates `slip_test`) |
| Real Ollama | `uv run pytest -m ollama` | Ollama + `qwen2.5:3b` |
| End-to-end on the running stack | `SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 uv run pytest -m e2e` | Full stack + Ollama; uploads and then deletes a synthetic paper |
| Frontend (from `frontend/`) | `npm ci && npm run lint && npm run typecheck && npm test && npm run build` | — |

Use `127.0.0.1`, not `localhost`, in database URLs on Windows (IPv6 resolution stalls connections).

## 5. What failures look like

| Situation | What you see |
|-----------|--------------|
| PostgreSQL stopped | `/ready` 503, `database: unreachable or not migrated`; API calls 503 "The database is unavailable…" |
| Ollama not running / unreachable | `/ready` shows `ollama: unreachable`; Q&A 503 "Ollama is not reachable…; start Ollama to use Q&A"; search still works |
| Model not pulled | Q&A 503 "model … not installed"; run `ollama pull qwen2.5:3b` |
| Models still downloading | `/ready` 503 with `embedding_model: loading` or `reranker: loading` |
