# ADR-0005: In-process ingestion jobs backed by a database job table

- Status: Accepted (2026-10-08, M1)

## Context

Ingesting a paper (download, extract, chunk, embed) takes seconds to minutes and must not block API requests
(IR-08). The platform runs on one machine for a small team. Options: Celery/RQ with Redis, a separate worker
process polling the DB, or an in-process thread pool.

## Decision

- Jobs are rows in `ingestion_jobs` with explicit states (`queued → fetching → extracting → chunking → embedding →
  ready | failed`). Each transition is committed so clients can poll `GET /api/v1/jobs/{id}`.
- Execution uses a `ThreadPoolExecutor` inside the API process (`app/services/jobs.py`), default 1 worker
  (`SLIP_INGESTION_WORKERS`, max 4) to bound CPU/memory use from embedding.
- A partial unique index allows at most one in-flight job per source reference; duplicate requests return the
  existing job (HTTP 200 instead of 202).
- All derived data for a paper is written in one transaction at the end; failures leave no partial chunks.
- On startup, non-terminal jobs are marked `failed` with "Interrupted by a server restart" because the in-memory
  queue does not survive restarts. Users re-request the import (explicit retry UI is M4).

## Alternatives rejected

- Celery + Redis: adds a broker and a worker deployment for a single-user workload; no measured need.
- Separate polling worker process: cleaner isolation, but doubles the processes to run and document. Revisit if
  ingestion measurably degrades search latency (NFR-04 measurements in M3).

## Consequences

- Simple to run and hand over. Jobs are lost (but clearly marked failed) on restart.
- Embedding work shares the API process's CPU; search latency during ingestion must be measured in M3.
