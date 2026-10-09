"""Retrieval stage profile and redundancy analysis for the RAG audit (NFR-03, NFR-04).

Times the ``hybrid_rerank`` stages with the production functions and parameters: query
embedding, dense SQL and BM25 SQL (each measured alone), the hybrid call (dense + BM25 + RRF, as in
production), and the cross-encoder. Also measures redundancy in the final ranking: neighbouring
chunks of one document (adjacent ordinals share ``chunk_overlap_tokens``) and exact duplicates.
"""

import itertools
import time
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.evaluation.dataset import EvalDataset
from app.evaluation.metrics import percentile
from app.retrieval.embedding import Embedder
from app.retrieval.rerank import RerankerProtocol
from app.retrieval.search import (
    ChunkHit,
    search_bm25_chunks,
    search_chunks,
    search_hybrid_chunks,
)

STAGES = ("embed", "dense", "bm25", "hybrid", "rerank")


def _adjacent_pairs(hits: list[ChunkHit]) -> int:
    keys = {(h.chunk.document_id, h.chunk.ordinal) for h in hits}
    return sum(1 for doc, ordinal in keys if (doc, ordinal + 1) in keys)


def profile_retrieval(
    dataset: EvalDataset,
    sessions: sessionmaker[Session],
    embedder: Embedder,
    reranker: RerankerProtocol,
    top_k: int,
    candidate_multiplier: int,
    rrf_k: int,
) -> dict[str, Any]:
    candidate_k = max(top_k * candidate_multiplier, 20)
    stages: dict[str, list[float]] = {name: [] for name in STAGES}
    adjacent = duplicates = 0
    for item in dataset.items:
        marks = [time.perf_counter()]
        vector = embedder.embed([item.question])[0]
        marks.append(time.perf_counter())
        with sessions() as session:
            search_chunks(session, vector, candidate_k)
            marks.append(time.perf_counter())
            search_bm25_chunks(session, item.question, vector, candidate_k)
            marks.append(time.perf_counter())
            # The production fusion call (runs dense + BM25 again, then RRF).
            fused = search_hybrid_chunks(
                session, vector, item.question, candidate_k, None, candidate_k, rrf_k
            )
            marks.append(time.perf_counter())
        final = reranker.rerank(item.question, fused, top_k)
        marks.append(time.perf_counter())
        for name, (start, end) in zip(STAGES, itertools.pairwise(marks), strict=True):
            stages[name].append((end - start) * 1000)
        adjacent += _adjacent_pairs(final)
        duplicates += len(final) - len({h.chunk.text for h in final})
    return {
        "config": {"top_k": top_k, "candidate_k": candidate_k, "rrf_k": rrf_k},
        "metrics": {
            **{
                f"{name}_ms_p{p}": round(percentile(values, p), 1)
                for name, values in stages.items()
                for p in (50, 95)
            },
            "queries": len(dataset.items),
            "adjacent_chunk_pairs_in_top_k": adjacent,
            "queries_x_top_k": len(dataset.items) * top_k,
            "exact_duplicate_texts_in_top_k": duplicates,
        },
    }
