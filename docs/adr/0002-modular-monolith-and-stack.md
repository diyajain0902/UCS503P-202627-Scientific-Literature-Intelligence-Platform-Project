# ADR-0002: Modular monolith backend, separate SPA frontend, monorepo layout

- Status: Accepted (2026-10-08)

## Context

The proposal names FastAPI, React, PostgreSQL + pgvector, PyMuPDF, sentence-transformers, Docker Compose, and
GitHub Actions. The repository was empty apart from the proposal. Team size is two; deployment target is one machine.

## Decision

- Monorepo: `backend/` (Python package `app`), `frontend/` (React + TypeScript + Vite), `docs/`, `eval/`.
- Backend is one FastAPI process with layered packages (see `docs/architecture/overview.md`). No microservices,
  no message broker.
- Python tooling: `uv` for environments and a lockfile (`uv.lock`), Ruff (lint + format), mypy `--strict`, Pytest.
- Frontend tooling: Vite scaffold defaults retained — oxlint (shipped by the current Vite template) for linting,
  `tsc` strict for type checking, Vitest + Testing Library + jsdom for tests.
- Settings via `pydantic-settings` with `SLIP_` env prefix.

## Alternatives considered

- Separate ingestion worker service: rejected for now; heavy embedding work runs in a background executor inside the
  API process with bounded concurrency (to be detailed in ADR for M1 jobs). Revisit if ingestion measurably blocks queries.
- ESLint instead of oxlint: oxlint is what the Vite template ships, is fast, and covers React hooks rules; switch only
  if a needed rule is missing.
- Poetry/pip-tools instead of uv: uv is installed, fast, and manages the Python version too (ADR-0004).

## Consequences

- One deployable backend keeps setup simple for handover.
- Module boundaries are enforced by review and tests, not process isolation.
