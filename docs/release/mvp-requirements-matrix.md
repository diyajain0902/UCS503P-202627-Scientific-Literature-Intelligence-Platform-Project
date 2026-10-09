# MVP Requirements Matrix

Final acceptance, 2026-10-09. The stack was rebuilt from `docs/mvp-final-acceptance` (commit `96cd1fb`) and run
with real PostgreSQL + pgvector, MiniLM, the cross-encoder, and Ollama `qwen2.5:3b`. "Live" means it was
exercised against the running application in this acceptance run (log excerpts in `mvp-acceptance-report.md` §2).
Statuses: **Verified** · **Implemented but unverified** · **Partially implemented** · **Failed** · **Blocked** ·
**Deferred**.

Priority comes from `docs/requirements/functional-requirements.md`. Required FRs and all IRs are the mandatory MVP
criteria.

## Functional requirements

| ID | Priority | Expected behaviour | Verification procedure | Actual result | Evidence | Status |
|----|----------|--------------------|------------------------|---------------|----------|--------|
| FR-01 | Required | Search arXiv by query and/or ID, show metadata | Live `GET /arxiv/search`; import by ID; unit tests | Query "dense passage retrieval" returned 3 papers with versions and an "already imported" flag; import by ID OK. **Defect found and fixed:** title queries containing stop words returned 0 results. After the fix, "attention is all you need" returns 10 results, though not the exact paper in the top 10 (arXiv ranking). arXiv also rate-limited this IP (429) during the run, surfaced as a 502 with a readable message | `test_arxiv.py` (32 pass, incl. new regression test); live log | Verified |
| FR-02 | Required | Import metadata + PDF; idempotent on `arxiv_id` | Live import `2004.04906v3`, then import again | Job states fetching → embedding → ready; the second import left 1 paper | Live; `test_ingestion_pipeline.py` | Verified |
| FR-03 | Required | Validated PDF upload, safe storage | Live upload of a real 5-page paper; non-PDF and oversized probes | Upload → ready (21 chunks); non-PDF 422; 51 MB 422 and 60 MB 413 (step 5b); stored as `<sha256>.pdf` | Live; `test_corpus_management.py` | Verified |
| FR-04 | Required | Page-aware extraction; text traceable to page and offset | `check_provenance` on every stored PDF in the live database | 4 documents, 210 chunks, 53 multi-page, **0 problems** | Live; `test_pdf.py`; step 4: 1,654 eval chunks, 0 problems | Verified |
| FR-05 | Required | Deterministic chunking; multi-page chunks record all pages | Provenance check; determinism tests | `page_start`/`page_end` correct for all 210 live chunks | `test_chunking.py`; identical retrieval metrics across 4 commits | Verified |
| FR-06 | Required | MiniLM 384-dim embeddings | SQL over live chunks | 210/210 chunks have embeddings; all `vector_dims` = 384 | Live SQL; `test_real_model.py` | Verified |
| FR-07 | Required | PostgreSQL + pgvector with constraints and migrations | Fresh database migrated 0001→0006; drift test | Schema 0006; `alembic check` and down/up round trip pass | `test_db_schema.py`; reproducibility report | Verified |
| FR-08 | Required | Ranked passages with score, chunk ID, paper, pages; corpus filter | Live search | DistilBERT passages ranked with pages, char spans, scores | Live; `test_search_integration.py` (4 modes) | Verified |
| FR-09 | Required | Grounded Q&A with local Ollama | Live Q&A | "DistilBERT is 40% smaller and 60% faster than BERT", 3.4 s | Live; `test_qa_ollama.py` (3 pass) | Verified |
| FR-10 | Required | Citations resolved server-side; never shown valid when unresolved | SQL on the live answer and all stored answers; UI inspector | Cited P1/P3 contain "40%" and "60%"; snapshots = chunks; 12/12 stored citations resolve; inspector shows "pp. 4–5" | Live SQL; browser; step 4: 422/422 | Verified |
| FR-11 | Required | Explicit abstention | Live unsupported question | "Kubernetes…" → insufficient evidence before any model call; the unanswerable eval subset gets 9/10 correct abstentions | Live; step 4 report | Partially implemented: abstention works, but **1/10 false answers** (RA-01) and no "uncertain" status (RA-05) |
| FR-12 | Required | Single-paper summary with provenance | Live `POST /papers/{id}/summary` | 5 claims, all with valid citations, 8.2 s. Every claim cites the same 6 passages (not claim-specific) | Live; `test_analysis_integration.py` | Verified (with that quality limitation) |
| FR-13 | Required | Cross-paper synthesis with per-claim citations | Live synthesis (DistilBERT + BERT) | 1 claim, valid citations to both papers | Live | Verified |
| FR-14 | Required | Structured extraction; cited or `unknown` | Live extraction | 6 fields, each cited (e.g. "retains 97% of BERT performance on GLUE", cites P8) | Live; tests | Verified. Values are not guaranteed correct (M5: a table value misread) |
| FR-15 | Required | Comparison table with caveats | Live compare (DistilBERT, DPR) | Table with 6 fields per paper and caveats | Live | Verified |
| FR-16 | Required | Corpus list, filters, details, delete | Live filters (source, year, title, category), details, delete | Filters correct; delete 204 then 404; file removed; history keeps snapshots | Live; UI two-step delete tested in M4 | Verified |
| FR-17 | Required | Job states, actionable errors, retry | Live job polling; tests | States observed; failure messages readable; retry tested | Live; `test_failed_job_can_be_retried` | Verified |
| FR-18 | Required | Query history with answers, citations, config, latency | Live `GET /qa`, UI History | 19 entries with status, latency, citations; answers reopen | Live; browser | Verified |
| FR-19 | Required | Retrieval eval harness on a versioned, **manually** labelled set | Step 4 audit | Harness works and is reproducible. **Labels are assistant-written, 0 human-reviewed** (ADR-0007) | `docs/evaluation/` | Partially implemented |
| FR-20 | Required | Answer-quality evaluation | Step 4 audit | Citation validity, abstention, latency and a local self-judge are measured; no human spot checks | `docs/evaluation/rag-evaluation-report.md` | Partially implemented |
| FR-21 | Required | CI retrieval gate | CI | Gates run; `main` @ `4d31e7b` green; `1ab4a0b` failed on arXiv 429 (fixed on the reproducibility branch, not yet observed in CI) | GitHub Actions | Verified |
| FR-22 | Recommended | Dashboard | Live `/stats`; browser | Counts and recent jobs shown | Live; browser | Verified |
| FR-23 | Recommended | Read-only settings | Live `/settings` | Models, limits, generation options; no secrets. Does **not** show the search mode or reranker model | Live | Partially implemented |
| FR-24 | Recommended | Hybrid dense + BM25 | Eval + live | R@5 0.725 (hybrid) | Experiment log | Verified |
| FR-25 | Optional | Cross-encoder rerank if better within the latency budget | Eval + live | R@5 0.875, but costs ~0.9 s, outside the NFR-03 budget | ADR-0008 | Verified (adopted despite the latency cost; decision recorded) |
| FR-26 | Optional | OCR | — | Scanned PDFs rejected with a clear error | `test_scanned_upload_fails_job_and_discards_file` | Deferred |

## Infrastructure requirements

| ID | Expected | Actual result / evidence | Status |
|----|----------|--------------------------|--------|
| IR-01 | Versioned REST API, error envelope, pagination, OpenAPI | `/api/v1`; envelopes for 404/422/500/503 probed live | Verified |
| IR-02 | Env config, `.env.example`, no secrets in git | Fresh clone worked from `.env.example`; no secrets in history | Verified |
| IR-03 | Docker Compose stack | Rebuilt and run; fresh-clone setup verified | Verified |
| IR-04 | GitHub Actions CI | 6 jobs; `main` green at `4d31e7b` | Verified |
| IR-05 | Liveness + per-dependency readiness | `/ready` shows database, embedding model, reranker, Ollama; tested with DB and Ollama down | Verified |
| IR-06 | JSON logs with request IDs, no content | Log scan (step 5b) | Verified |
| IR-07 | Ollama adapter with timeouts and error mapping | Ollama unreachable → 503 with reason (live) | Verified |
| IR-08 | Background ingestion | Jobs run asynchronously (live) | Verified |
| IR-09 | Setup, troubleshooting, handover docs | README, `docs/operations/`, `docs/handover.md`, this release set | Verified |

## Non-functional requirements

| ID | Target | Measured | Status |
|----|--------|----------|--------|
| NFR-01 | Recall@5 ≥ 0.80 | 0.875 (`hybrid_rerank`; assistant labels; mode chosen on the same set) | Verified on this set, with caveats |
| NFR-02 | MRR reported | 0.701 | Verified |
| NFR-03 | p95 Q&A ≤ 3 s | Warm p95 4.43–4.50 s (eval runs); single live answers 2.4–5.7 s | **Failed** |
| NFR-04 | Search p95 reported | 1,955 ms (`hybrid_rerank`, top 10); 49 ms dense | Verified |
| NFR-05 | ≥ 99% availability over a defined pilot window | 52/52 probes in a 25.5-minute window | Partially implemented (window too short to support the target) |
| NFR-06 | 100% displayed citations resolve | 12/12 live, 422/422 eval | Verified |
| NFR-07 | Abstention precision/recall reported | Recall 0.90, precision 0.64–0.82 | Verified (reported) |
| NFR-08 | Deterministic chunks and rankings | Identical retrieval metrics across 4 commits; provenance 0 problems | Verified |
| NFR-09 | Config recorded with answers and runs | Answers record model, prompt, embedding, retrieval block | Verified |
| NFR-10 | Security controls | Step 5b: passed with limitations; SEC-02 (superuser DB role), SEC-05 (no parse timeout) open | Partially implemented |
| NFR-11 | Privacy | No content or secrets in logs; no hosted LLM | Verified |
| NFR-12 | Resource bounds | All bounded except PDF parse time and backend JSON body size | Partially implemented |
| NFR-13 | Runs on the reference machine | Every run in this report | Verified |
| NFR-14 | CI green | Green on `main` @ `4d31e7b`; one earlier red run (arXiv 429) | Verified |
| NFR-15 | Accessibility | Role/label-based tests; no manual accessibility audit | Implemented but unverified |
| NFR-16 | Search works without Ollama; explicit 503 | Live: search 200, Q&A 503 with reason | Verified |
