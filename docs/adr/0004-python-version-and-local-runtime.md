# ADR-0004: Python 3.12 via uv; Docker required for PostgreSQL + pgvector

- Status: Accepted for Python; Docker installation pending (team action). DB tests run in CI meanwhile.
- Date: 2026-10-08

## Context

Reference machine (verified 2026-10-08): Windows 11, system Python 3.14.5, Node 24.16, npm 11.13, uv 0.11.7,
Ollama 0.34.4. **Not installed:** Docker, PostgreSQL client (`psql`), GitHub CLI, WSL.
PyTorch (required by sentence-transformers) and some scientific packages often lag new Python releases on Windows.

## Decision

- Backend pins `requires-python = ">=3.12,<3.13"`; `backend/.python-version` = `3.12`. uv installs a managed
  CPython 3.12 (done: 3.12.13) without touching the system Python. CI uses the same version via `setup-uv`.
- PostgreSQL + pgvector runs from the official `pgvector/pgvector` Docker image via Docker Compose (M1).
  Native Windows pgvector builds are possible but fragile and harder to hand over; not chosen.
- Embeddings use CPU PyTorch wheels by default (MiniLM is small); GPU VRAM is reserved for the Ollama model.

## Consequences

- **Blocker for M1:** Docker Desktop (which needs WSL2 or Hyper-V) must be installed by the team. Until then,
  database-dependent integration tests cannot run locally; they can still run in GitHub Actions using a
  `pgvector/pgvector` service container.
