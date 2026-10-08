# Audit — Security and Privacy, first pass (protocol step 5a)

- **Date:** 2026-10-09. **Commit audited:** `main` at `4eff300` plus M7 changes on
  `feature/m7-release-readiness`.
- **Requirements:** NFR-10, NFR-11, NFR-12; `CLAUDE.md` §6.
- **Threat model:** a single user on one Windows machine. All ports bind to `127.0.0.1`. Inputs that can be
  hostile: uploaded PDFs, arXiv content, text retrieved from papers (prompt injection), model output, and HTTP
  requests from local processes or browser pages (CSRF/CORS).
- **Method:** code review of every input boundary and every `logger.*` call; a search for SQL built from strings;
  `git ls-files` for secrets and artifacts; `pip-audit` and `npm audit`; header check of the running stack with
  `curl -I`; checking the database role.
- **Auditor:** the AI assistant. This audit is not independent. **Step 5b** (second pass before release) is still
  to be done after S1 and S2 are decided.
- **Note:** this audit was scheduled after M4. It was carried out late, in M7.

## 1. Results by `CLAUDE.md` §6 item

| Item | Result |
|------|--------|
| Upload size cap | Pass. Streamed read stops past 50 MB (code review; there is no automated test of the byte cap). nginx allows 55 MB. |
| Page cap | Pass (200 pages; tested). |
| MIME + magic bytes | Partial. Magic bytes plus a full parse are checked; the client `Content-Type` is not (S7, accepted). |
| Encrypted / malformed PDF rejection | Pass (tested). |
| Processing timeouts | **Fail (S2).** No wall-clock limit on PyMuPDF parsing. Ollama has a 60 s timeout and arXiv has its own timeout. |
| Server-generated filenames, no traversal | Pass (`test_storage.py::test_rejects_unsafe_keys`). |
| Request / query / pagination limits | Pass for fields. **Partial:** JSON body size is not capped at the backend (S4). |
| Ingestion concurrency limit | Pass (1 worker, configurable 1–4). |
| Parameterized SQL | Pass. No string-built SQL in `app/`; BM25 terms are reduced to `\w` before `to_tsquery` (unit-tested). |
| Prompt injection | Pass. Delimiting, neutralisation, system rules, constrained JSON, server-side citation resolution; real-model test `test_qa_ollama.py` (manual). |
| Secrets | Pass. `.env` ignored; `git ls-files` lists no `.env`, PDFs (except the proposal's own `main.pdf`), model weights or dumps. The settings endpoint exposes no credentials (tested). |
| Logging | Pass. Every `logger.*` call logs event names, IDs, counts or durations; none logs question text, passages or document contents. `logger.exception` tracebacks could include exception messages, and none of the raise sites builds messages from document text. |
| Hosted LLM | Pass. No hosted provider exists in code. |
| Artifacts not committed | Pass (`.gitignore`; checked with `git ls-files`). |
| CORS | Pass (allow-list; tested in `test_health.py`). |
| Least-privilege DB role | **Fail (S1).** The app uses `slip`, which is a PostgreSQL superuser (`rolsuper = t`, checked). |
| Authorization | Not implemented (S3). Acceptable only while the tool stays single-user and local. |
| Dependency scanning in CI | **Was missing; added in M7** (`dependency-audit` job). Local results: Python 0 known vulnerabilities (`torch` +cpu not auditable); npm 0 vulnerabilities. |

## 2. Changes made during this audit

- nginx now sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a
  same-origin Content-Security-Policy, and `server_tokens off`. Verified with `curl -I` on the rebuilt stack. The
  UI was exercised in a browser with no console errors.
- The reranker model failing to load now returns 503 (`DependencyUnavailableError`) instead of an unhandled 500
  (unit-tested).
- `dependency-audit` CI job.

## 3. Open findings (details in `docs/security.md` §3)

| ID | Severity (local use) | Needs |
|----|----------------------|-------|
| S1 superuser DB role | Medium (High if exposed) | **Team decision.** Splitting into migration and runtime roles changes deployment and needs a manual step on the existing volume. |
| S2 no PDF parse timeout | Medium | Run parsing in a killable subprocess. |
| S3 no auth | Low locally; blocks sharing | Required before any shared deployment. |
| S4 backend port bypasses nginx body cap | Low | Drop the published `8000` port or add a body-size middleware. |
| S5 model revisions not pinned | Medium | Pin Hugging Face revisions. |
| S6 torch not auditable | Low | Check advisories by hand when updating. |
| S7 Content-Type not checked | Info | Accepted. |
