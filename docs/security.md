# Security and Privacy

Maintained document (`CLAUDE.md` §6). Requirements: NFR-10, NFR-11, NFR-12. Audit history: `docs/audits/`.
Scope: a **single-user tool on one machine**. Every published port binds to `127.0.0.1`. Nothing is exposed to a
network, and there is no authentication. Exposing the service beyond localhost needs the open items in §3
resolved first, plus explicit team authorization.

## 1. Controls in place

| Area | Control | Where | Evidence |
|------|---------|-------|----------|
| Upload size | Streamed read, rejected above `SLIP_MAX_PDF_BYTES` (50 MB); nginx `client_max_body_size 55m` | `api/v1/corpus.py`, `frontend/nginx.conf` | Code review only (no automated test of the byte cap) |
| Upload content | `%PDF-` magic bytes; corrupt, encrypted, zero-page, > `SLIP_MAX_PDF_PAGES` (200) rejected **before** a job is created; text-less (scanned) PDFs fail the job and the file is deleted | `ingestion/pdf.py`, `services/ingestion.py` | `test_pdf.py` (pages, encrypted), `test_corpus_management.py` (page limit, encrypted, scanned) |
| Duplicates | SHA-256 of the bytes; re-upload → 409 | `services/ingestion.py` | `test_corpus_management.py` |
| Storage paths | Server-generated keys from SHA-256 only; keys validated; resolved path must stay under the storage root; user filenames are never used as paths | `ingestion/storage.py` | `test_storage.py::test_rejects_unsafe_keys` |
| Outbound HTTP (SSRF) | arXiv client allow-lists HTTPS hosts, re-checks redirects, caps size, rate-limits; XML parsed with `defusedxml` | `ingestion/arxiv.py` | `test_arxiv.py::test_client_follows_allowed_redirect_only` |
| SQL injection | ORM / bound parameters only; no SQL built from strings in `app/`; BM25 query terms reduced to `\w` characters before `to_tsquery` | `retrieval/search.py` | code search (no `text(f…)`); `test_search_hybrid.py::test_bm25_terms_strip_tsquery_syntax` |
| Prompt injection | Retrieved text is delimited, delimiter-like text neutralised, system prompt forbids following passage instructions; JSON schema constrains output; citations resolved server-side against supplied passages only | `generation/prompts.py`, `generation/analysis_prompts.py`, `generation/citations.py` | `test_generation.py`; `test_qa_ollama.py` (real model, manual) |
| Resource bounds | Query ≤ 1,000 chars; search top_k ≤ 50; Q&A top_k ≤ 10, question ≤ 1,000 chars, context ≤ 12,000 chars; generation ≤ 512 tokens, `num_ctx` 4096, timeout 60 s; 1 ingestion worker; pagination caps; synthesis/compare 2–5 papers | `core/config.py`, `api/v1/*` | `test_api_validation.py` (search, pagination), `test_config.py` |
| CORS | Allow-list from `SLIP_CORS_ORIGINS`; methods GET/POST/DELETE; header `Content-Type` only | `main.py` | `test_health.py` |
| HTTP headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP `default-src 'self'` (inline styles allowed), `server_tokens off` | `frontend/nginx.conf` | Verified with `curl -I` in M7 (progress log) |
| Errors | Typed domain errors → status + `{"error": {code, message}}`; no stack traces in responses | `core/errors.py` | `test_search_integration.py::test_unknown_ids_return_404_envelope` |
| Secrets | `.env` git-ignored; only `.env.example` committed; Compose refuses to start without `POSTGRES_PASSWORD`; settings endpoint shows no credentials | `.gitignore`, `docker-compose.yml`, `api/v1/corpus.py` | `git ls-files` check (M7 audit); `test_corpus_management.py::test_stats_and_settings` |
| Logging (NFR-11) | JSON logs with event names, IDs, counts, durations; no question text, passage text, or document contents | all `logger.*` calls | Code review of every log call (M7 audit) |
| No hosted LLM (NFR-11) | Generation only through the local Ollama adapter; no hosted provider exists in code; Ollama down → 503 | `generation/ollama.py`, ADR-0001 | `test_generation.py::test_ollama_bad_responses`, `test_qa_integration.py` |
| Artifacts | PDFs, model weights, DB dumps, caches git-ignored | `.gitignore` | `git ls-files` check (M7 audit) |
| Container | Backend runs as non-root UID 10001; all ports on `127.0.0.1` | `backend/Dockerfile`, `docker-compose.yml` | — |
| Dependencies | `pip-audit` (locked Python deps) and `npm audit --audit-level=high` in CI | `.github/workflows/ci.yml` (`dependency-audit`) | M7 local run: 0 known vulnerabilities (torch not auditable, see §3) |

## 2. Data handled

- Paper PDFs and their extracted text (stored in PostgreSQL and the storage volume). Uploaded PDFs may be
  private documents: they never leave the machine. The only outbound calls are to arXiv (import/search) and to
  Hugging Face on first model download.
- Questions, answers, and analyses are stored with evidence snapshots (Q&A history). There is no user identity.

## 3. Open risks (accepted for local single-user use unless stated)

| ID | Risk | Status |
|----|------|--------|
| S1 | The app connects to PostgreSQL as `slip`, which is a **superuser** (the image's `POSTGRES_USER`). This breaks the least-privilege rule in `CLAUDE.md` §6. | **Open, needs a team decision.** The proposed fix is a separate migration-owner role and a runtime role limited to DML. That changes how the stack is deployed and how its credentials are handled, and an existing data volume needs a one-off manual step. |
| S2 | PDF parsing has no wall-clock timeout. A pathological PDF within the size and page caps could hold the single ingestion worker. | Open. Bounded by the 50 MB / 200-page caps and one worker. A fix needs parsing in a subprocess so it can be killed. |
| S3 | No authentication or authorization. Anyone who can reach `127.0.0.1:8080` or `:8000` can use every endpoint, including delete. | Accepted for local use. **Blocks any shared or public deployment.** |
| S4 | The backend port `127.0.0.1:8000` bypasses nginx's body limit. FastAPI JSON bodies have no size cap; field limits apply only after parsing. | Accepted (local only). Remove the published port, or add a body-size middleware, before any wider exposure. |
| S5 | Hugging Face models are pinned by name, not revision, and downloaded at runtime. | Open (supply-chain and reproducibility). Pin `revision=` or vendor the weights into the image. |
| S6 | `torch` comes from the PyTorch CPU index (`+cpu` build) and is skipped by `pip-audit`. | Accepted. Check PyTorch security advisories by hand when bumping the lock. |
| S7 | Upload `Content-Type` is not checked. | Accepted. The magic-byte check plus a full PyMuPDF open is stronger than trusting the client-sent type. |
