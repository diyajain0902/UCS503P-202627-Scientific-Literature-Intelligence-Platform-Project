# Architecture Overview

## Context

A single-user/small-team research tool running on one machine (reference: 16 GB RAM, RTX 3050 Laptop 4 GB VRAM,
Ryzen 7 7435HS, Windows 11). All models run locally. The only outbound network dependency is the arXiv API.

```
┌──────────────┐  HTTP /api/v1   ┌──────────────────────────── backend (FastAPI) ────────────────────────────┐
│  frontend    │ ──────────────► │ api/ ──► services/ ──► ingestion/  retrieval/  generation/  evaluation/    │
│ React + Vite │ ◄────────────── │                │            │           │            │                   │
└──────────────┘                 │                └──────────► db/ (SQLAlchemy repositories) ◄───────────────┘
                                 └──────────────────────────────┬──────────────┬──────────────┬─────────────┘
                                                                │              │              │
                                                    PostgreSQL + pgvector   Ollama (local)  arXiv API (HTTPS)
                                                                         sentence-transformers (in-process)
```

## Components (backend `app/`)

| Package | Responsibility | May depend on |
|---------|----------------|---------------|
| `api/v1/` | Routes, request/response schemas, HTTP error mapping. No SQL, no prompts. | `services/`, `core/` |
| `services/` | Use-case orchestration: ingestion jobs, search, Q&A, summaries, extraction. Transactions. | everything below |
| `ingestion/` | arXiv client, upload validation, PDF extraction, chunking. Pure where possible. | `core/` |
| `retrieval/` | Embedding model wrapper, vector search queries, (later) hybrid/rerank. | `db/`, `core/` |
| `generation/` | LLM provider interface + Ollama adapter, prompt templates, output schemas, citation validation. No DB access. | `core/` |
| `evaluation/` | Metrics (Recall@k, MRR, citation validity, abstention), eval runner, run records. | `services/`, `retrieval/` |
| `db/` | SQLAlchemy models, session management, repositories. | `core/` |
| `core/` | Settings, logging, error types. | — |

Rule: no upward imports (e.g. `ingestion` must not import `api`). Enforced by review now; an import-linter
contract can be added in M7 if violations appear.

## Key flows

1. **Ingest (M1):** `POST /papers/arxiv` → create job (queued) → background worker: fetch metadata + PDF →
   extract pages → chunk → embed (batched) → store in one transaction per document → job `ready` / `failed`.
2. **Search (M1):** embed query → pgvector cosine search (HNSW) with optional corpus filter → ranked chunks with provenance.
3. **Q&A (M2):** validate question → search → relevance threshold (abstain early if nothing passes) → bounded,
   delimited context → Ollama (JSON output) → schema validation → citation resolution → persist query/answer → respond.

## Decisions

See `docs/adr/`. Data model: `docs/architecture/data-model.md`.
