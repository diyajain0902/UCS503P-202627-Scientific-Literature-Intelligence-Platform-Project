# ADR-0008: Hybrid BM25 + Dense Retrieval with Cross-Encoder Reranking

- **Status**: Accepted (M6, 2026-10-09). **Corrected 2026-10-09 (M7)**, see "Correction" below.
- **Deciders**: Paarth Ganesh, Diya Jain
- **Requirements**: FR-24, FR-25, NFR-01, NFR-03

## Context

The M3 dense baseline (`all-MiniLM-L6-v2`, HNSW cosine) reached Recall@5 0.700 on `eval/qa_v1.json`, below
NFR-01 (≥ 0.80). Questions that hinge on exact terms (names, acronyms, numbers) were the typical misses.

## Decision

1. **Sparse retrieval:** PostgreSQL full-text search. Query terms are reduced to alphanumeric tokens and OR-ed
   (`to_tsquery('english', 't1 | t2 | …')`; `websearch_to_tsquery` only if no term survives), ranked with
   `ts_rank_cd` over a stored generated column `chunks.text_tsv` with a GIN index (migration 0006; 0005's
   expression index is replaced, see Correction).
2. **Fusion:** Reciprocal Rank Fusion over the dense and sparse candidate lists, `k = 60`, equal weights,
   candidate pool `max(top_k × 4, 20)` per list; ties broken by chunk ID.
3. **Reranking:** `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU) rescores the fused pool; the best `top_k` are
   returned. Default `SLIP_SEARCH_MODE=hybrid_rerank`; `dense`, `bm25`, `hybrid` remain selectable per request.
4. **Score semantics:** `ChunkHit.score` / API `score` is always the query–chunk **cosine similarity**, so
   `qa_min_score` keeps its M3 calibration. The ordering score of the mode (BM25 rank, RRF score, or
   cross-encoder logit) is reported separately as `rank_score`.

## Evaluation results

`eval/qa_v1.json` (40 answerable, 10 unanswerable; labels assistant-written, unreviewed, ADR-0007), 20-paper
corpus (1,654 chunks), top_k 10, Windows reference machine on AC power, CPU inference, commit `192ac2b`
(after migration 0006). Latency is the server-side search time per query.

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | p50 | p95 | Run record |
|---|---|---|---|---|---|---|---|
| dense (baseline) | 0.200 | 0.700 | 0.775 | 0.416 | 46 ms | 53 ms | `20261008T203718Z_retrieval_192ac2b.json` |
| bm25 | 0.300 | 0.525 | 0.650 | 0.393 | 56 ms | 91 ms | `20261008T203750Z_retrieval_192ac2b.json` |
| hybrid (RRF) | 0.375 | 0.725 | 0.825 | 0.527 | 102 ms | 137 ms | `20261008T203825Z_retrieval_192ac2b.json` |
| **hybrid_rerank** | **0.575** | **0.875** | **0.925** | **0.701** | 1,853 ms | 2,021 ms | `20261008T204032Z_retrieval_192ac2b.json` |

Q&A with the default mode (`20261008T204611Z_qa_b173e72.json`, see `docs/evaluation.md` §7): answer rate 0.875,
cited-relevant 0.725, citation validity 1.00, **1/10 false answers on unanswerable questions** (M5: 0/10), warm
p95 4.5 s.

## Consequences

- NFR-01 is met on this set **by `hybrid_rerank` only** (`hybrid` alone: 0.725). The mode was chosen on the same
  50 questions it is measured on and the labels are unreviewed, so 0.875 is an optimistic estimate.
- **Latency cost:** the cross-encoder dominates search time (~37 ms per candidate pair on this CPU; 40 pairs at
  top_k 10, 24 pairs at the Q&A default top_k 6). This puts NFR-03 (p95 ≤ 3 s) out of reach on this machine
  with qwen2.5:3b (measured, M7). Choosing `SLIP_SEARCH_MODE=hybrid` trades recall for latency.
- One more model (~90 MB) is downloaded on first use and loaded at start-up (warm-up thread).
- Retrieval configuration (mode, RRF, weights, reranker) is recorded with every answer, analysis, and eval run.

## Alternatives considered

- Dense only (fails NFR-01). Hybrid without reranking (fails NFR-01 on this set, fast).
- A separate BM25 library or index (another moving part; PostgreSQL FTS is already present).

## Correction (M7, 2026-10-09)

The M6 version of this ADR contained an evaluation table whose numbers did not match any committed run record
(e.g. BM25 Recall@5 0.650 vs. 0.525 recorded; hybrid 0.825 vs. 0.725; all latencies under 100 ms vs. 0.65–3.0 s
recorded) and stated that it used `websearch_to_tsquery` and stayed "well under 100 ms p95". Those statements
were wrong and have been replaced by the re-run above. M7 also fixed two defects in the M6 implementation:

1. In `hybrid_rerank` mode the cross-encoder logit replaced `score`, so `qa_min_score` (0.30, a cosine
   threshold) was compared with logits; BM25-only hits in `hybrid` carried a `ts_rank_cd` value as `score`.
2. BM25 recomputed `to_tsvector` for every matching row (636 ms for one query); the 0005 index only helped
   filtering. Migration 0006 stores the vector (19 ms for the same query).
