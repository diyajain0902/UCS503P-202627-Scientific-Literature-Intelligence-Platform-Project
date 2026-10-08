# Audit — RAG Evaluation (protocol step 4)

- **Date:** 2026-10-09. **Commit audited:** `main` at `4eff300` (M6 merged) plus M7 fixes on
  `feature/m7-release-readiness`.
- **Requirements:** FR-19–FR-21, NFR-01–NFR-04, NFR-06, NFR-07, NFR-09.
- **Scope:** the evaluation harness (`backend/app/evaluation/`), dataset and corpus (`eval/`), run records,
  reported numbers (`docs/evaluation.md`, progress log, ADR-0008), and the retrieval/Q&A behaviour they measure.
- **Method:** code reading; re-running retrieval in all four modes and Q&A twice; tracing every reported number to
  a run record; checking the eval database against the documentation.
- **Auditor:** the AI assistant, which also wrote the labels and most of the code. This audit is **not
  independent**; the team should review it.
- **Note:** this audit was scheduled after M3. It was carried out late, in M7, covering M3 to M6.

## 1. Findings

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| R1 | **Fabricated numbers in ADR-0008 (M6).** Its evaluation table matched no run record: BM25 R@5 0.650 vs. 0.525 recorded, hybrid 0.825 vs. 0.725, rerank R@1 0.525 vs. 0.575, and all latencies under 100 ms vs. 0.65–3.0 s recorded. It also claimed NFR-01 was met by hybrid without reranking. This breaks `CLAUDE.md` §4 ("never fabricate … metrics"). | Critical | **Fixed.** ADR-0008 was rewritten from re-run records, with a correction notice. |
| R2 | **Threshold applied to the wrong score.** In `hybrid_rerank` (the default since M6) `ChunkHit.score` held the cross-encoder logit, but `qa_min_score` 0.30 is a cosine threshold. Evidence admission therefore depended on an uncalibrated scale. In `hybrid`, BM25-only hits carried `ts_rank_cd` values. | Critical | **Fixed.** `score` is now always cosine similarity and `rank_score` holds the ordering score. Regression tests: `test_reranker.py`, `test_search_hybrid.py`, `test_search_integration.py::test_every_search_mode_reports_cosine_scores`. |
| R3 | Q&A was not re-evaluated after the default retrieval changed in M6. | High | **Fixed.** Two Q&A runs (`docs/evaluation.md` §7). |
| R4 | **New false answer** under `hybrid_rerank`: q050 (DistilBERT energy) is answered with a LLaMA figure in both runs. M5 had 0/10 false answers. | High | **Open.** Prompt and abstention changes are outside the M7 scope, and tuning them on the test set would be leakage. Candidate fix for a later milestone: require the claim's subject to match the question's entity, evaluated on a held-out set. |
| R5 | **Model selection on the test set.** The search mode was chosen on the same 50 questions that report NFR-01 = 0.875. | Medium | Open, disclosed. A held-out question set is needed for an unbiased number. |
| R6 | **Labels are unreviewed.** All 50 items are `labeler: ai-assistant`, `review_status: unreviewed` (ADR-0007), and the auditor wrote them. | Medium | Open. Human review of a sample (for example 15 items) is the main missing data. It cannot be done by the assistant. |
| R7 | Corpus size in the docs was wrong: 1,207 pages / 1,634 chunks stated, the database holds 399 / 1,654. The database was built once (2026-10-08 13:39–13:42 UTC) and never rebuilt. | Low | **Fixed** in `docs/evaluation.md`. |
| R8 | The M6 BM25 and hybrid latencies were measured with migration 0005 not applied to the eval database (it was still at 0004). Even with 0005, ranking recomputed `to_tsvector` per row. | Medium | **Fixed** (migration 0006). BM25 p50 went from 653 to 56 ms. |
| R9 | An unexplained M6 run record (`20261008T195921Z`, bm25 R@5 0.075) was committed without mention. | Low | Disclosed in `docs/evaluation.md` §7. Kept for transparency. |
| R10 | The retrieval gate checked the default mode against the dense threshold (also CI/CD C1). | High | **Fixed.** |
| R11 | Run records did not record retrieval settings (mode, RRF, reranker). | Medium | **Fixed** (NFR-09). |
| R12 | The relevance rule needs a whole evidence quote inside one chunk. A quote that crosses a chunk boundary counts as a miss; the 38-token overlap only partly mitigates this. | Low | Open, accepted. This makes Recall conservative, not optimistic. |
| R13 | The groundedness judge is the answering model itself (qwen2.5:3b). It rated the q050 false answer "supported" because it checks support, not relevance. | Medium | Open, disclosed. Human spot checks are still outstanding. |
| R14 | Latency targets depend on power state and background load; NFR-03 is not met (warm p95 4.4–4.5 s on AC). | — | Reported honestly. NFR-03 stays **not met**. |

## 2. What was verified as correct

- **Metric code:** Recall@k and MRR have unit tests on hand-computed cases (`test_eval_metrics.py`, 12 tests
  passing).
- **Retrieval determinism:** dense, BM25 and hybrid_rerank metrics reproduce exactly across M3, M6 and M7 runs
  (CI/CD audit §3).
- **Citation validity is 1.00 in every Q&A run.** Citations are resolved server-side against the supplied
  passages; the E2E test also checks that a citation is shown as valid only if its label was supplied.
- **Abstention on 9 of the 10 unanswerable items**, both runs.
- **The corpus manifest hash** matches between run records (`6f5c0efa…`).

## 3. Verdict

The harness is sound and reproducible. Two critical problems from M6 (R1, R2) are fixed and covered by tests.
The headline NFR-01 result (Recall@5 0.875) is real but optimistic (R5, R6). Q&A quality improved except for one
new false answer (R4), and NFR-03 is not met. The most valuable missing data is a human review of the labels plus
a small held-out question set.
