# Retrieval and RAG Experiment Log

Fixed data for every experiment: corpus `nlp-core` v1 (20 papers, 1,654 chunks) and dataset `nlp-core-qa` v1
(40 answerable, 10 unanswerable; assistant-labelled, unreviewed). Hardware: Ryzen 7 7435HS, 16 GB RAM, Windows 11,
AC power, all retrieval models on CPU, Ollama `qwen2.5:3b` on an RTX 3050 4 GB. Relevance is judged per chunk (see
the methodology document). Run records are in `eval/runs/`.

## E1 — Dense baseline (M3; reproduced in M6, M7 and this audit)

- **Configuration:** MiniLM-L6-v2 (384-dim, normalised), cosine distance, exact ordering, top_k 10.
- **Results:** R@1 0.200, R@5 **0.700**, R@10 0.775, MRR 0.416. Search p50/p95 42/49 ms
  (`20261008T214635Z_retrieval_03fb705.json`, clean commit). Identical metrics in `3eab94d`, `0006bbd` and
  `192ac2b`.
- **Failures (12 at k = 5):** in all 12 the gold paper was in the top 5 but the relevant passage ranked lower (9 of
  them not in the top 10 at all).

## E2 — BM25 alone (M6, re-measured M7)

- **Hypothesis:** exact-term matching helps questions that name specific terms.
- **Change:** PostgreSQL FTS, OR of alphanumeric terms, `ts_rank_cd`.
- **Results:** R@1 0.300, R@5 0.525, R@10 0.650, MRR 0.393, p50/p95 56/91 ms (`20261008T203750Z`).
- **Decision:** not used alone. Better at rank 1 than dense, worse at 5 and 10.

## E3 — Hybrid RRF (dense + BM25)

- **Change:** RRF with k = 60, equal weights, 40 candidates per list.
- **Results:** R@1 0.375, R@5 0.725, R@10 0.825, MRR 0.527, p50/p95 102/137 ms (`20261008T203825Z`).
- **Decision:** a small gain (+1 item at R@5) for about 60 ms. Kept as the fast alternative mode.

## E4 — Hybrid + cross-encoder rerank (current default)

- **Change:** `cross-encoder/ms-marco-MiniLM-L-6-v2` rescores the fused candidates (40 at top_k 10; 24 at the
  Q&A top_k of 6).
- **Results:** R@1 **0.575**, R@5 **0.875**, R@10 0.925, MRR **0.701**, p50/p95 1,734/1,955 ms
  (`20261008T214832Z_retrieval_03fb705.json`, clean commit; identical metrics in `0006bbd` and `192ac2b`).
- **Failures (5 at k = 5):** q002 (rank 10), q018 (rank 7), q026, q029, q036 (not in the top 10). The gold paper is
  in the top 5 for all five.
- **Cost:** stage profile at the Q&A top_k of 6 (`20261008T214608Z_profile-retrieval_03fb705.json`): embed
  17/30 ms, dense SQL 29/36 ms, BM25 SQL 36/66 ms, hybrid call 61/85 ms, **cross-encoder 895/985 ms** (p50/p95).
  The reranker is about 92% of retrieval time (embed + hybrid + rerank, p50).
- **Decision (ADR-0008):** adopted for recall. This is the only configuration that reaches NFR-01 on this set.
  **Caveat:** it was chosen on the test set.

## E5 — Q&A with E4 retrieval (M7)

- `20261008T204611Z_qa_b173e72.json` (with judge) and `20261008T205117Z_qa_b173e72.json`.
- **Answer rate** 0.875 and 0.95 (M5 with dense: 0.80). **Cited-relevant** 0.725 and 0.75 (M5: 0.55).
- **Citation validity** 52/52 and 57/57.
- **Abstention:** recall 9/10 in both runs; **false answers 1/10 (q050)**.
- **Warm latency** p50/p95 3.10/4.50 s and 3.06/4.43 s; cold start 8.1–12.0 s.
- **Decision:** NFR-03 not met; see the report.

## E6 — Redundancy in the context (this audit)

- **Measurement:** in the top 6 for 50 questions (300 slots), there are **47 pairs of neighbouring chunks** from
  the same document. Neighbours share 38 overlapping tokens. There are 0 exact duplicate texts.
- **Implication:** part of the 12,000-character context repeats text, and two labels can cover the same sentence.
- **Not acted on:** de-duplicating neighbours (or merging them, small-to-big) is a candidate experiment that needs
  a held-out set.

## Not run

- **Small-to-big chunking** (planned for M6). Deferred.
- **Reranker candidate-pool size sweep** (e.g. 12 vs. 24 vs. 40). This is the most direct latency lever. It must be
  tuned on a held-out set, not on this one.
- **HNSW vs. exact search:** at this corpus size PostgreSQL chooses an exact sequential scan (see report finding
  RA-06), so HNSW parameters currently have no effect.
