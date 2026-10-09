# MVP Acceptance Report (protocol step 7)

Scientific Literature Intelligence Platform: UCS503P (2026–27), Thapar Institute of Engineering and Technology.
Authors: Paarth Ganesh, Diya Jain. Lab instructor: Ms. Paramveer Kaur.

- **Date:** 2026-10-09.
- **Build accepted:** branch `docs/mvp-final-acceptance` at commit `96cd1fb`, built on `main` `4d31e7b` plus the
  reproducibility fixes.
- **Reviewer:** the AI assistant, acting as QA reviewer at the team's request. **Not independent**: it also wrote
  most of the code. All results come from runs in this session on the reference machine (Windows 11, Ryzen 7
  7435HS, 16 GB RAM, RTX 3050 4 GB; Docker Desktop; Ollama `qwen2.5:3b`).

## Outcome: **MVP READY WITH DOCUMENTED LIMITATIONS**

Every mandatory user journey works against the real running application:

- import, upload and page-aware extraction
- embeddings and search
- grounded Q&A with local Ollama, with citations verified against source passages and pages
- abstention
- analyses, corpus management and history
- graceful handling of invalid input and of missing services

No release-blocking defect remains. One core-journey defect was found and fixed: arXiv title search with stop words
returned nothing. The limitations below are real and must be disclosed with the submission:

- the latency target is missed
- 1 in 10 unanswerable test questions gets a wrong-paper answer
- evaluation labels are AI-written and have no human review yet
- Ollama is exposed on this machine's network until the host setting is changed

## 1. Core workflows tested (live, real components)

| # | Journey | Result |
|---|---------|--------|
| 1 | Discover a paper via arXiv | Query returned papers with versions and "already imported" flags. Title-query defect fixed (§4). arXiv rate-limited this IP at times; the app showed "arXiv returned HTTP 429" (502) and did not crash |
| 2 | Import from arXiv (`2004.04906v3`) | fetching → embedding → ready; re-import idempotent (1 paper) |
| 2b | Upload a scientific PDF (DistilBERT, 5 pages) | ready, 21 chunks |
| 3 | Page provenance | Re-extraction of all 4 stored PDFs: 210 chunks, 53 spanning pages, **0 problems** (text at the recorded span, recorded pages, words present on those PDF pages) |
| 4 | Embeddings persisted | 210/210 chunks, all 384-dim; chunker `tokwin-v1 \| w256 \| o38` |
| 5 | Semantic search | DistilBERT size and speed passages ranked first, with pages, character spans and scores |
| 6 | Grounded Q&A | "DistilBERT is 40% smaller and 60% faster than BERT", citations P1 (p. 4) and P3 (pp. 4–5) |
| 7 | Citations vs. sources | Both cited passages contain "40%" and "60%"; evidence snapshots equal the stored chunk text, pages and paper; 12/12 stored citations resolve. UI inspector opens "[P3] DistilBERT (uploaded PDF), pp. 4–5" |
| 8 | Unsupported questions | "Kubernetes…" → insufficient evidence before any model call. An answerable DPR question also abstained (known retrieval miss, q026) |
| 9 | Invalid input and missing services | Non-PDF, empty query, over-long question, bad arXiv ID, 1-paper synthesis → 422 with a field message. DB stopped → `/ready` 503 and API 503 "The database is unavailable…"; recovered on restart. Ollama unreachable → Q&A 503 "Ollama is not reachable…", search 200 |
| — | Summary, extraction, synthesis, comparison | All completed with valid citations on the real model (8.2 s / 6.0 s / 3.1 s / compare OK) |
| — | Corpus filters, details, delete | Correct counts; delete 204 → 404; stored file removed; history keeps evidence snapshots |
| — | UI | Dashboard, Ask (submit → result with model, prompt and latency), History → saved answer → citation inspector. The browser console showed only network errors from the deliberate outage tests |

The two papers added for acceptance were deleted afterwards; the corpus is back to its original 2 papers.

## 2. Test and build results (this acceptance run)

| Check | Result |
|-------|--------|
| Ruff, ruff format, mypy strict (78 files) | Pass |
| Backend unit (mocked embedder, LLM, arXiv) | **140 passed** |
| Integration + real MiniLM (PostgreSQL + pgvector; `SLIP_REQUIRE_TEST_DATABASE=1`) | **83 passed**, 0 skipped |
| Real Ollama (`-m ollama`) | **3 passed** |
| Live arXiv (`-m network`) | 1 failed during the arXiv 429 period, **1 passed** on rerun |
| End-to-end on the rebuilt stack (`-m e2e`) | **7 passed** |
| Frontend: oxlint, `tsc`, Vitest, production build | Pass; **24 passed**; build OK |
| `npm audit` | First attempt: npm registry error; rerun: 0 vulnerabilities |
| `docker compose config`; images rebuilt and started | Pass |
| CI on `main` @ `4d31e7b` | All 6 jobs green |

## 3. RAG evaluation results (step 4; `docs/evaluation/rag-evaluation-report.md`)

Recall@1 / @5 / @10 = 0.575 / **0.875** / 0.925, MRR 0.701 (`hybrid_rerank`, 50 assistant-labelled questions, 0
human-reviewed). Citation validity 1.00. Abstention recall 0.90, false answers 1/10. Warm Q&A p95 4.4–4.5 s.
High findings, both open: RA-01 wrong-paper answers; RA-02 a valid citation that does not support its claim
(2 of 14 spot-checked claims).

## 4. Defects found and fixed in this acceptance run

| Defect | Severity | Fix | Verification |
|--------|----------|-----|--------------|
| arXiv discovery by title returned 0 results whenever the text contained stop words ("attention is all you need"): arXiv does not index them and every term was AND-ed | High (core journey 1) | Stop words removed from the query unless nothing else remains | `test_search_query_drops_stop_words_so_titles_match`; live query now returns 10 results |

Fixed in the preceding reproducibility check and re-verified here:

- database outage → 503
- `/ready` includes the reranker
- CI retries arXiv 429
- CI fails, rather than skips, when its test database is missing

## 5. Security and reproducibility status

- **Security (step 5b):** passed with documented limitations. Open: **SEC-01 High**, Ollama listening on the
  network (a host setting; fix steps in `docs/security/mvp-security-audit.md` §6). Also SEC-02 superuser DB role,
  SEC-05 no PDF parse timeout, SEC-08 unpinned model revisions. No authentication, which is acceptable only for
  local single-user use.
- **Reproducibility:** fresh clone outside OneDrive → install, migrate, start, ingest, search, answer, cite:
  verified (`docs/operations/mvp-reproducibility-report.md`). First start about 15 minutes (model downloads).

## 6. Outstanding defects and limitations

See `mvp-known-limitations.md`. Release-relevant items the team must be able to explain:

1. **NFR-03 not met** (p95 ≈ 4.5 s vs. 3 s).
2. **RA-01 / RA-02:** wrong-paper answers and unsupported-but-cited claims.
3. **Labels not human-reviewed (FR-19/FR-20).** `CLAUDE.md` §5 requires human spot checks of groundedness.
4. **SEC-01** host fix.
5. **The availability pilot was only 25 minutes.**

## 7. Demonstration sequence (about 10 minutes, stack already running and `/ready` all green)

1. **Dashboard:** status bar with database, embedding model, reranker and Ollama all green.
2. **Add papers → Import by arXiv ID** `1706.03762v7` (or search "transformer attention" and import from the list).
3. **Add papers → Upload** a PDF you are allowed to use; watch the job reach *Ready*.
4. **Search passages:** "how much smaller and faster is DistilBERT than BERT" (or a question about your paper);
   point out pages and scores.
5. **Ask:** "What BLEU score does the big Transformer model achieve on the WMT 2014 English-to-German translation
   task?" Click chip **P1** to show the page-8 passage containing 28.4.
6. **Ask an unsupported question:** "Which Kubernetes setup was used to serve the models in production?" →
   *Insufficient evidence*.
7. **Corpus → paper → Summarise / Extract;** **Compare** two papers.
8. **History:** reopen an answer; **Settings:** show the local model configuration.

Rehearse the questions beforehand. Q&A sometimes abstains on answerable questions (FM-08); the system prefers
abstaining to guessing.

## 8. Deferred (intentionally, not post-MVP work started)

OCR for scanned PDFs (FR-26); authentication and multi-user; claim-level entailment checking; a held-out evaluation
set and human label review; small-to-big chunking; latency work (reranker pool size, GPU inference); public
deployment (needs authorization).
