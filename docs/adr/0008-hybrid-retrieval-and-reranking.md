# ADR-0008: Hybrid BM25 + Dense Retrieval with Cross-Encoder Reranking

- **Status**: Approved
- **Deciders**: Paarth Ganesh, Diya Jain
- **Date**: 2026-10-09
- **Requirements**: FR-24, FR-25, NFR-01

## Context and Problem Statement

In Milestone 3 evaluation against the 20-paper NLP benchmark corpus (`eval/qa_v1.json`), the baseline dense retrieval system using `all-MiniLM-L6-v2` embeddings achieved:
- **Recall@1**: 0.200
- **Recall@5**: 0.700
- **Recall@10**: 0.775
- **MRR**: 0.416
- **Latency (p50 / p95)**: 47.5 ms / 62.8 ms

This fell short of **NFR-01** (Recall@5 $\ge$ 0.800). Technical queries containing specific terminology, rare keyword acronyms, or exact formula tokens were frequently missed by pure dense embedding search.

## Decision Drivers

1. **Recall Improvement**: Achieve Recall@5 $\ge$ 0.800 on the benchmark evaluation set without overfitting.
2. **Precision and Ranking**: Improve MRR (Mean Reciprocal Rank) so relevant passages appear higher in top-$k$ context.
3. **Latency Constraints**: Maintain low search latency within the overall response budget.
4. **Local Hardware Constraint**: Rely strictly on in-process / PostgreSQL local capabilities without external API dependencies.

## Decision

We adopt **Hybrid Search with Reciprocal Rank Fusion (RRF)** combined with **Cross-Encoder Reranking**:

1. **PostgreSQL Full-Text Search (BM25 Sparse)**:
   - Added GIN index on `to_tsvector('english', text)` in `chunks` table (Migration `0005`).
   - Executes `websearch_to_tsquery('english', query)` and scores candidates with `ts_rank_cd`.

2. **Reciprocal Rank Fusion (RRF)**:
   - Fetches candidate pools ($N=40$) from both dense HNSW vector search and BM25 sparse search.
   - Combines candidate ranks using RRF formula:
     $$RRF\_score(d) = \frac{1}{k + r_{dense}(d)} + \frac{1}{k + r_{sparse}(d)}$$
     with fusion parameter $k=60$.

3. **Cross-Encoder Reranking**:
   - Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` to score candidate $(query, passage)$ pairs.
   - Re-ranks top candidates before returning the final top-$k$ results.

## Evaluation Results

Evaluated on `eval/qa_v1.json` (40 answerable, 10 unanswerable questions over 20 NLP papers):

| Retrieval Strategy | Recall@1 | Recall@5 | Recall@10 | MRR | p50 Latency | p95 Latency | NFR-01 Met? |
|---|---|---|---|---|---|---|---|
| Dense Vector (Baseline) | 0.200 | 0.700 | 0.775 | 0.416 | 47.5 ms | 62.8 ms | No |
| BM25 Sparse Search | 0.350 | 0.650 | 0.725 | 0.478 | 12.1 ms | 24.3 ms | No |
| Hybrid RRF (Dense + BM25) | 0.425 | 0.825 | 0.875 | 0.583 | 55.4 ms | 78.1 ms | **Yes** |
| Hybrid RRF + Cross-Encoder Rerank | **0.525** | **0.875** | **0.900** | **0.662** | 68.2 ms | 95.6 ms | **Yes** |

## Consequences

- **Positive**:
  - **NFR-01 Satisfied**: Recall@5 increases from 0.700 to **0.875** ($\Delta +17.5\%$).
  - **MRR Improved**: MRR jumps from 0.416 to **0.662** ($\Delta +59\%$), placing relevant passages at position 1 or 2 far more consistently.
  - Search latency remains well under 100 ms p95 on standard CPU hardware.
- **Negative / Trade-offs**:
  - Requires loading `cross-encoder/ms-marco-MiniLM-L-6-v2` (~90 MB VRAM / RAM).
  - Migration 0005 adds a GIN index on `chunks` text column (~15% DB index size increase).
