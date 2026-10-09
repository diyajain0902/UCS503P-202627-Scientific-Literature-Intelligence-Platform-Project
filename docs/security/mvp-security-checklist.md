# MVP Security Checklist

Re-run before every demo or submission. Status as of 2026-10-09 (step 5b); details in `mvp-security-audit.md`.
Legend: ✅ verified · ⚠️ open / accepted risk · ❌ failing.

## Uploads and storage

- ✅ Non-PDF, corrupt, encrypted and over-page-limit PDFs rejected before a job is created (422)
- ✅ Files over 50 MB rejected by the backend (422); over 55 MB by nginx (413)
- ✅ Stored filenames are server-generated (`<sha256>.pdf`); client filenames are never paths
- ✅ Unsafe storage keys rejected; no temp files left behind
- ✅ Scanned PDFs: job fails and the file is deleted
- ⚠️ No wall-clock timeout on PDF parsing (SEC-05)
- ⚠️ Client filename can become the display title (SEC-07; rendered as text)

## API and errors

- ✅ Field limits: query/question ≤ 1,000 chars, `top_k` bounds, pagination ≤ 100, search mode allow-list
- ✅ Validation errors return 422 with a field message; unknown IDs return 404
- ✅ Unexpected errors return a fixed `internal_error` envelope; details only in the server log
- ⚠️ JSON body size not capped when the backend is called directly on `:8000` (SEC-06)

## Database

- ✅ ORM / bound parameters only; BM25 terms sanitised; LIKE wildcards escaped
- ✅ Injection-style inputs return 200 or 422 and leave the tables intact
- ⚠️ The app uses a superuser role (SEC-02)

## Secrets and logs

- ✅ `.env` git-ignored and never committed; DB password absent from the git history
- ✅ `/settings` exposes no credentials
- ✅ Logs contain event names, IDs and counts. No questions, passages, document text or query strings
  (`--no-access-log`)

## Network exposure

- ✅ Docker ports bound to `127.0.0.1` (8080, 8000, 5432)
- ✅ CORS allows only configured origins
- ✅ nginx security headers (CSP, nosniff, frame DENY, no-referrer)
- ❌ **Ollama listens on `0.0.0.0:11434` with Public-profile firewall Allow rules (SEC-01, High)**. Fix with
  `mvp-security-audit.md` §6, step 4, then re-check: `netstat -ano | findstr 11434`
- ⚠️ No authentication: never tunnel or port-forward the app

## LLM and RAG integrity

- ✅ Retrieved text delimited and neutralised; injected instructions not followed (real-model test)
- ✅ Citations resolved server-side against the supplied passages only; unresolved citations never shown as valid
- ✅ Invalid model output or Ollama failure gives an explicit error or 503, never a fabricated answer
- ✅ No hosted LLM anywhere in the code
- ⚠️ A valid citation does not guarantee semantic support; wrong-paper answers are possible (RA-01, RA-02)

## Dependencies

- ✅ `npm audit`: 0 vulnerabilities
- ✅ `pip-audit`: no known vulnerabilities (runs in the CI `dependency-audit` job)
- ⚠️ `torch` (+cpu) not auditable; model revisions not pinned (SEC-08)

## Commands to re-verify

```bash
netstat -ano | findstr ":11434 :8000 :8080 :5432"
cd backend && uv run pytest -m "not integration and not model and not network and not ollama and not e2e"
cd backend && SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 uv run pytest -m e2e
cd frontend && npm audit
curl -sI http://localhost:8080/ | findstr /i "content-security x-frame nosniff"
```
