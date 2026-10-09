# MVP Security and Privacy Audit (protocol step 5b)

- **Date:** 2026-10-09.
- **Code audited:** `main` at `1ab4a0b`, plus the fixes on `chore/step5b-mvp-security-audit`.
- **Reviewer:** the AI assistant, at the team's request. This is a **practical MVP review**: code reading, the
  existing test suites, targeted probes against the locally running Docker stack, and a host exposure check. **It
  is not a penetration test or a comprehensive security audit.** No fuzzing, no dependency source review, no threat
  modelling beyond the single-user local scope.
- **Scope assumption (unchanged):** single user, one Windows machine, no authentication, all application ports on
  `127.0.0.1`. The first pass (step 5a) is in `docs/audits/2026-10-09-security-privacy-audit.md`; the controls
  inventory is in `docs/security.md`.

## 1. Components reviewed

| Component | Files |
|-----------|-------|
| PDF upload and validation | `api/v1/corpus.py` (`upload_pdf`), `ingestion/pdf.py`, `services/ingestion.py` |
| Storage, filenames, temporary files | `ingestion/storage.py`, `services/ingestion.py`, `services/corpus.py` (delete) |
| API input validation and errors | `api/v1/*`, `core/errors.py`, `core/config.py` |
| Database access and configuration | `retrieval/search.py`, `services/*`, `db/`, `docker-compose.yml`, `docker/db-init/` |
| Secrets and logging | `.env.example`, `.gitignore`, `core/logging.py`, every `logger.*` call, `backend/Dockerfile` |
| CORS and exposed services | `main.py`, `docker-compose.yml`, `frontend/nginx.conf`, host listening ports |
| Ollama prompts, untrusted retrieved text, model output | `generation/prompts.py`, `generation/analysis_prompts.py`, `generation/ollama.py`, `services/qa.py` |
| Citation validation and attribution | `generation/citations.py`, Q&A persistence |
| Dependencies | `backend/uv.lock`, `frontend/package-lock.json` |

## 2. Tests actually executed

### Automated suites (after the fixes)

| Suite | Result |
|-------|--------|
| Backend unit (`not integration/model/network/ollama/e2e`) | **137 passed** (includes 3 new security regression tests) |
| Backend integration + real embedding model (`integration or model`, PostgreSQL 17 + pgvector 0.8.0) | **81 passed** |
| Real local model (`pytest -m ollama`, includes instructions embedded in a passage) | **3 passed** |
| End-to-end on the rebuilt stack (`pytest -m e2e`) | **7 passed** |
| Ruff, ruff format, mypy strict (78 files) | Pass |
| Frontend: oxlint, `tsc`, Vitest | Pass; **24 passed** |
| `npm audit` | 0 vulnerabilities |
| `pip-audit` (locked runtime deps; M7 run, lock unchanged since) | No known vulnerabilities; `torch` (+cpu build) not auditable |

### Live probes against the Docker stack (`http://127.0.0.1:8080/api/v1`)

| Probe | Result |
|-------|--------|
| Non-PDF bytes uploaded as `application/pdf` | 422 "File is not a PDF (missing %PDF- header)" |
| Truncated PDF | 422 "PDF is corrupt or unreadable" |
| 51 MB file (above the 50 MB backend cap) | 422 "File is larger than the 50 MB limit" |
| 60 MB file (above nginx's 55 MB cap) | 413 from nginx |
| Upload named `../../../../etc/passwd.pdf` | Stored as `<sha256>.pdf` inside `/data/storage` (mode 600); no file elsewhere; the name kept only as a display label |
| Malformed JSON; 5,000-char query; `top_k` 1000; unknown `search_mode`; `limit` 100000 | 422 with a field-level message; no stack trace or path |
| `x'; DROP TABLE papers; --` in BM25 and hybrid search; tsquery operators only (`& \| ! :* ()`) | 200, no error; `papers` table intact |
| Title filter `%';--` | 0 matches (LIKE wildcards escaped) |
| Unknown / invalid / path-like paper IDs | 404 / 422 / 404, no internal details |
| arXiv ID `../../evil.com/x` | 422 "not a valid arXiv identifier" |
| 5,000-char question | 422 |
| CORS preflight from `http://evil.example` | 400, no `Access-Control-Allow-Origin` |
| CORS preflight from `http://localhost:8080` | Allowed |
| `/settings` response | No password or database URL |
| Backend log (5,690 lines) for question text, document text, DB password, tracebacks | None found. **Query strings were found in uvicorn's access log** (finding SEC-03) |
| DB password in the full git history (`git log --all -p`) | 0 occurrences; no `.env` tracked |
| Listening ports on the host | App ports on `127.0.0.1` only. **Ollama on `0.0.0.0:11434` and `[::]:11434`** (finding SEC-01) |

## 3. Findings

| ID | Severity | Finding | Evidence | Status |
|----|----------|---------|----------|--------|
| SEC-01 | **High** | **Ollama is reachable from the local network without authentication.** The machine-wide `OLLAMA_HOST=0.0.0.0`, Windows Firewall has inbound *Allow* rules for `ollama.exe` on the Public profile, and the active network is Public. Anyone on the same network can run prompts and use Ollama's model-management API (pull and delete models). | `netstat`; `[Environment]::GetEnvironmentVariable('OLLAMA_HOST','Machine')`; `Get-NetFirewallRule` (read-only checks) | **Open: needs the owner.** This is a host OS and firewall setting outside the repository; changing system security settings is reserved for the machine owner. Steps in §6 |
| SEC-02 | Medium | App connects to PostgreSQL as a **superuser** (`slip`, `rolsuper = t`) | Step 5a S1 | Open (team decision: separate migration and runtime roles). The port is on `127.0.0.1` only |
| SEC-03 | Low | uvicorn's access log wrote full query strings (e.g. the corpus title search `?q=…`) in addition to the app's own request log | Live log scan | **Fixed:** `--no-access-log` in `backend/Dockerfile`. Verified on the rebuilt stack: probe query string 0 times in the log, app request lines still written. Regression test `test_container_does_not_write_an_access_log_with_query_strings` |
| SEC-04 | Low | Unhandled exceptions fell back to Starlette's plain-text 500. No details leaked, but there was no envelope and no structured log entry | Code review | **Fixed:** catch-all handler returns `{"error": {"code": "internal_error", …}}` with a fixed message and logs the exception server-side. Test `test_unexpected_errors_return_a_fixed_envelope_without_internal_details` (asserts no password, URL, path, or traceback in the body) |
| SEC-05 | Medium | No wall-clock timeout on PDF parsing | Step 5a S2 | Open; bounded by the 50 MB / 200-page caps and 1 ingestion worker |
| SEC-06 | Low | The backend port `127.0.0.1:8000` bypasses nginx's body limit; FastAPI JSON bodies are not size-capped | Step 5a S4 | Open (local only) |
| SEC-07 | Low | The client filename (e.g. `../../../../etc/passwd.pdf`) is kept as the paper's display title when no other title exists | Live probe; deliberate M4 behaviour, asserted by `test_user_file_name_never_becomes_a_path` | Accepted: it is never used as a path, and React renders it as text |
| SEC-08 | Medium | Hugging Face models pinned by name, not revision; downloaded at first start | Step 5a S5 | Open |
| SEC-09 | Info | No authentication or authorization | Scope | Accepted for MVP. **Must not be exposed beyond localhost** |
| SEC-10 | Info | `docs/security.md` said the upload byte cap had no automated test. The test exists (`test_invalid_uploads_rejected_before_any_job[too-large]`) | Code review | Corrected |

**No critical findings. One high finding (SEC-01).** It is a host configuration issue, not an application
defect. It cannot be fixed from the repository and is left to the owner (§6).

## 4. Protections verified

| Requirement | Verified by |
|-------------|-------------|
| Invalid or oversized PDFs rejected safely, before a job or file is created | Probes above; `test_invalid_uploads_rejected_before_any_job`, `test_encrypted_upload_rejected`, `test_scanned_upload_fails_job_and_discards_file` |
| Uploads cannot write outside storage | Probe; `test_storage.py::test_rejects_unsafe_keys`; `test_user_file_name_never_becomes_a_path` |
| Temporary files cleaned up | `test_storage.py::test_no_temp_files_left_behind`; scanned-PDF file discarded (test above) |
| Secrets not committed or logged | Git history scan; log scan; `test_stats_and_settings` |
| Safe database queries | No string-built SQL in `app/`; injection probes; `test_bm25_terms_strip_tsquery_syntax` |
| Retrieved text treated as untrusted | Prompt review; `test_instructions_inside_passages_are_not_followed` (real model, passed) |
| Model citations validated against supplied evidence | `test_generation.py`, `test_qa_integration.py`; step 4 audit: 422/422 stored citations resolve to evidence of the same answer |
| Invalid model output and Ollama failures → explicit errors, not fabricated success | `test_ollama_bad_responses`, `test_malformed_model_output_is_an_error_not_an_answer`, `test_generation_failures_are_explicit_and_recorded` |
| App services not exposed publicly | Docker ports bound to `127.0.0.1` (checked with `docker ps` and `netstat`). **Ollama is the exception (SEC-01)** |
| Errors don't reveal secrets or paths | Probes; new catch-all handler and test |

## 5. Known limitations and residual risks

- **No authentication.** Any local process or user on this machine can use and delete data through the API.
- **The superuser DB role (SEC-02) and the missing parse timeout (SEC-05) remain.**
- **Unpinned model revisions (SEC-08).**
- **`torch` is not covered by `pip-audit`.**
- **Prompt-injection resistance** is tested with one real-model case. Model behaviour is probabilistic, and the
  step 4 audit found wrong-paper answers (RA-01) and claims whose cited passage does not support them (RA-02).
  These are integrity issues, not security exploits, but users must not treat answers as verified facts.
- **Browser-side protections** (CSP, frame denial) apply only through nginx on port 8080, not on `:8000/api/v1/docs`.
- **Not done:** penetration testing, fuzzing, dependency source review, a load or DoS test, and a multi-user
  threat model.

## 6. Running the MVP safely on your machine

1. Copy `.env.example` to `.env` and set a strong `POSTGRES_PASSWORD`. Never commit `.env`.
2. `docker compose up -d --build`. All app ports bind to `127.0.0.1`; don't change them to `0.0.0.0`.
3. Use the app at `http://localhost:8080` (nginx adds the security headers).
4. **Restrict Ollama to this machine (SEC-01).** Run these yourself in an **administrator** PowerShell. They change
   system settings, so review them first:

   ```powershell
   [Environment]::SetEnvironmentVariable('OLLAMA_HOST', '127.0.0.1', 'Machine')
   Get-NetFirewallApplicationFilter | Where-Object Program -like '*ollama*' | Get-NetFirewallRule | Disable-NetFirewallRule
   ```

   Then restart Ollama (quit it from the tray and start it again). Verify with `netstat -ano | findstr 11434`,
   which should show only `127.0.0.1:11434`, and with `curl http://localhost:8080/api/v1/ready`, which should show
   `ollama ok: true`.

   If the Docker backend can no longer reach Ollama through `host.docker.internal` after this, roll back with the
   steps below. Then keep the firewall rules disabled and set `OLLAMA_HOST` back to `0.0.0.0`. With the firewall
   blocking inbound traffic, the port is still unreachable from the network. The firewall rules are the part that
   matters.

   ```powershell
   [Environment]::SetEnvironmentVariable('OLLAMA_HOST', '0.0.0.0', 'Machine')
   Get-NetFirewallApplicationFilter | Where-Object Program -like '*ollama*' | Get-NetFirewallRule | Enable-NetFirewallRule
   ```
5. Don't expose ports 8000, 8080, 5432 or 11434 with tunnels or port forwards. The `ngrok` install found on this
   machine is relevant here. There is no authentication.
6. Upload only documents you are allowed to process; they stay in the local database and the `storage` volume.
7. Back up with `pg_dump` plus the `storage` volume (`docs/operations.md` §4); keep the dumps out of git.

## 7. Conclusion

**MVP security checks passed with documented limitations.** The application controls held under every probe, and
the two low-severity issues found were fixed and verified. The one **High** finding (SEC-01, Ollama exposed to the
local network) is a host setting outside the repository. It must be fixed by the machine owner using §6, step 4,
before the MVP is demonstrated on a shared or public network. Medium items SEC-02, SEC-05 and SEC-08 remain open
for a team decision.
