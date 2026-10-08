# Operations

How to run, configure, check, and recover the platform. Setup basics are in `README.md`; security in
`docs/security.md`. Target environment: one machine, Docker Compose, Ollama on the host (IR-03, IR-09).

## 1. Components

| Service | Image / process | Port (127.0.0.1) | State |
|---------|-----------------|------------------|-------|
| `db` | `pgvector/pgvector:0.8.0-pg17` | 5432 | volume `pgdata` (databases `slip`, `slip_test`; `slip_eval` if created) |
| `backend` | `backend/Dockerfile` (Python 3.12, uvicorn, non-root) | 8000 | volume `storage` (PDFs), `hf-cache` (models) |
| `frontend` | `frontend/Dockerfile` (nginx 1.27, built React app, `/api` proxy) | 8080 | none |
| Ollama | host process | 11434 | host model store (`qwen2.5:3b`) |

The backend runs `alembic upgrade head` on every start, then serves. Models load in a background thread:
MiniLM (embeddings), the cross-encoder (reranking), and the Ollama warm-up.

## 2. Start, stop, update

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose down
```

`docker compose down` keeps the volumes. `docker compose down -v` **deletes all data**, so don't run it on a
corpus you need.

**OneDrive:** builds from inside OneDrive can fail with `invalid file request` because of cloud placeholders. Either
move the repository out of OneDrive (recommended), or mirror it and build from the copy:

```powershell
robocopy . $env:TEMP\slip-build /MIR /XD node_modules .venv dist .git __pycache__ data "Project Proposal"
```

Then run `docker compose up -d --build` inside `%TEMP%\slip-build`. Robocopy exit codes 0–7 mean success.

**Readiness:** `GET http://localhost:8080/api/v1/ready` returns 200 only when the database (pgvector ≥ 0.8.0,
migrated), the embedding model, and Ollama are all ready. It also reports the schema revision (currently `0006`).

## 3. Configuration

Settings are `SLIP_`-prefixed environment variables (`backend/app/core/config.py`; example values in
`.env.example`). Compose passes `SLIP_OLLAMA_MODEL` and `SLIP_SEARCH_MODE` from the root `.env`. Settings that
matter most in operation:

| Setting | Default | Notes |
|---------|---------|-------|
| `SLIP_SEARCH_MODE` | `hybrid_rerank` | `hybrid` drops the cross-encoder: about 1.1 s faster per Q&A, Recall@5 0.725 instead of 0.875 |
| `SLIP_RERANKER_ENABLED` | `true` | If false, `hybrid_rerank` behaves like `hybrid` |
| `SLIP_OLLAMA_MODEL` | `qwen2.5:3b` | Recorded with every answer; changing it invalidates Q&A baselines |
| `SLIP_QA_MIN_SCORE` | `0.30` | Cosine threshold for evidence; calibrated in M3 |
| `SLIP_MAX_PDF_BYTES` / `SLIP_MAX_PDF_PAGES` | 50 MB / 200 | nginx allows 55 MB bodies |
| `SLIP_INGESTION_WORKERS` | 1 | 1–4 |
| `SLIP_CORS_ORIGINS` | `["http://localhost:5173"]` | Compose sets `["http://localhost:8080"]` |
| `SLIP_LOG_LEVEL` | `INFO` | JSON logs to stdout |

## 4. Database

- **Migrations:** `cd backend && uv run alembic upgrade head` (pointed at the target with `SLIP_DATABASE_URL`).
  Never edit an applied migration. 0006 adds a stored column and rewrites `chunks`; it took seconds on 1,654 chunks.
- **Backup** (a local file; never commit it, since `*.dump` is git-ignored):
  `docker compose exec db pg_dump -U slip -Fc slip > slip_backup.dump`
- **Restore** into an empty database: `pg_restore -U slip -d slip_restored slip_backup.dump`. Restoring over a live
  database is destructive and needs a deliberate decision.
- The uploaded PDFs live in the `storage` volume and must be backed up alongside the database dump.
- `slip_test` is a throwaway database: the integration tests drop and recreate its tables.

## 5. Checks and measurements

| What | Command (from `backend/` unless noted) |
|------|----------------------------------------|
| Unit / lint / types | see `README.md` §Checks |
| Integration | `SLIP_TEST_DATABASE_URL=postgresql+psycopg://slip:<pw>@127.0.0.1:5432/slip_test uv run pytest -m integration` |
| End-to-end on the running stack | `SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 uv run pytest -m e2e` (uploads a synthetic paper and deletes it at the end) |
| Retrieval eval | `SLIP_DATABASE_URL=…/slip_eval uv run python -m app.evaluation retrieval --search-mode hybrid_rerank` |
| Q&A eval | `… python -m app.evaluation qa [--judge]`. Plug in the laptop and keep other work off the machine; record both in the report |
| Availability (NFR-05) | from repo root: `python scripts/uptime_probe.py --minutes 60 --interval 30 --out eval/uptime/<name>.jsonl` |
| Summarise a probe log | `python scripts/uptime_probe.py --summarize eval/uptime/<name>.jsonl` |

**Availability definition (NFR-05).** Per probe, *search* is up if `POST /search` returns 200, and *Q&A* is up if
`/ready` reports every dependency ok. The Q&A part is a dependency proxy: the probe does not generate answers,
because they would fill the history. Gaps longer than twice the probe interval (for example the laptop sleeping)
are reported as unobserved and are not counted as either up or down.

## 6. Troubleshooting

See `README.md` §Troubleshooting. Additional operational cases:

| Symptom | Cause / action |
|---------|----------------|
| `/ready` → `ollama: not reachable` | Start Ollama on the host. Search keeps working (NFR-16); Q&A and analyses return 503. |
| Search 503 "Reranker model … could not be loaded" | First start without internet. Connect once, or set `SLIP_SEARCH_MODE=hybrid`. |
| Q&A slower than usual | Battery power (latency roughly doubles), the cold model (first question after 30 min idle, 8–12 s), or other load. |
| Upload job `failed` "PDF has little or no extractable text (likely scanned)" | Scanned PDF. OCR is not supported (FR-26 deferred). |
| Jobs `failed` "Interrupted by a server restart" | The backend restarted mid-job. Retry it under *Add papers → Recent ingestion jobs*. |
| `alembic` "Target database is not up to date" in tests | Run `alembic upgrade head` on that database. |
