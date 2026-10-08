"""Dense, BM25, and hybrid vector/text search over persisted chunks (FR-08, FR-24)."""

import re
import uuid
from dataclasses import dataclass, replace

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, Paper

# hnsw.iterative_scan (used below) was added in pgvector 0.8.0; older versions reject the setting.
MIN_PGVECTOR_VERSION = (0, 8, 0)


def parse_version(raw: str) -> tuple[int, ...]:
    """Parse a version like ``0.8.0`` into a comparable tuple; non-numeric parts end the parse."""
    parts: list[int] = []
    for piece in raw.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def installed_pgvector_version(session: Session) -> str | None:
    version: str | None = session.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one_or_none()
    return version


def pgvector_version_problem(version: str | None) -> str | None:
    """Return a user-readable problem if the installed pgvector cannot serve searches."""
    if version is None:
        return "pgvector extension not installed"
    if parse_version(version) < MIN_PGVECTOR_VERSION:
        required = ".".join(map(str, MIN_PGVECTOR_VERSION))
        return f"pgvector {version} is installed; {required} or newer is required"
    return None


@dataclass(frozen=True)
class ChunkHit:
    chunk: Chunk
    paper: Paper
    score: float
    """Cosine similarity between the query and chunk embeddings, in [-1, 1], in every search mode.
    Evidence thresholds (``qa_min_score``) are calibrated on this value."""
    rank_score: float | None = None
    """Mode-specific ordering score: BM25 ``ts_rank_cd``, RRF score, or cross-encoder logit.
    ``None`` for dense search, where ``score`` is the ordering score."""


def search_chunks(
    session: Session,
    query_vector: list[float],
    top_k: int,
    paper_ids: list[uuid.UUID] | None = None,
) -> list[ChunkHit]:
    """Dense semantic vector search via HNSW cosine distance (FR-08)."""
    session.execute(
        text("SELECT set_config('hnsw.ef_search', :ef, true)"), {"ef": str(max(40, top_k * 2))}
    )
    session.execute(text("SELECT set_config('hnsw.iterative_scan', 'strict_order', true)"))

    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(Chunk, Paper, distance)
        .join(Document, Chunk.document_id == Document.id)
        .join(Paper, Document.paper_id == Paper.id)
        .order_by(distance, Chunk.id)
        .limit(top_k)
    )
    if paper_ids:
        statement = statement.where(Paper.id.in_(paper_ids))
    return [
        ChunkHit(chunk=chunk, paper=paper, score=1.0 - float(dist))
        for chunk, paper, dist in session.execute(statement).all()
    ]


_TERM = re.compile(r"\W+")


def bm25_terms(query_text: str) -> list[str]:
    """Reduce a query to alphanumeric terms that are safe inside a ``to_tsquery`` OR expression."""
    terms = (_TERM.sub("", word) for word in query_text.split())
    return [term for term in terms if len(term) > 1]


def search_bm25_chunks(
    session: Session,
    query_text: str,
    query_vector: list[float],
    top_k: int,
    paper_ids: list[uuid.UUID] | None = None,
) -> list[ChunkHit]:
    """Sparse full-text search ranked by ``ts_rank_cd`` over the stored ``text_tsv`` column
    (GIN-indexed, migration 0006). Each hit also carries its cosine similarity (``score``).
    """
    terms = bm25_terms(query_text)
    if terms:
        tsquery = func.to_tsquery("english", " | ".join(terms))
    else:
        tsquery = func.websearch_to_tsquery("english", query_text)

    rank = func.ts_rank_cd(Chunk.text_tsv, tsquery).label("rank")
    distance = Chunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(Chunk, Paper, rank, distance)
        .join(Document, Chunk.document_id == Document.id)
        .join(Paper, Document.paper_id == Paper.id)
        .where(Chunk.text_tsv.op("@@")(tsquery))
        .order_by(rank.desc(), Chunk.id)
        .limit(top_k)
    )
    if paper_ids:
        statement = statement.where(Paper.id.in_(paper_ids))

    return [
        ChunkHit(chunk=chunk, paper=paper, score=1.0 - float(dist), rank_score=float(r))
        for chunk, paper, r, dist in session.execute(statement).all()
    ]


def search_hybrid_chunks(
    session: Session,
    query_vector: list[float],
    query_text: str,
    top_k: int,
    paper_ids: list[uuid.UUID] | None = None,
    candidate_k: int = 40,
    rrf_k: int = 60,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> list[ChunkHit]:
    """Hybrid search combining dense HNSW and BM25 FTS with Reciprocal Rank Fusion (RRF) (FR-24).

    Hits are ordered by RRF score (``rank_score``, ties broken by chunk ID); ``score`` stays the
    cosine similarity so evidence thresholds mean the same thing in every mode.
    """
    dense_hits = search_chunks(session, query_vector, candidate_k, paper_ids)
    bm25_hits = search_bm25_chunks(session, query_text, query_vector, candidate_k, paper_ids)

    rrf_scores: dict[uuid.UUID, float] = {}
    hit_map: dict[uuid.UUID, ChunkHit] = {}
    for hits, weight in ((dense_hits, dense_weight), (bm25_hits, sparse_weight)):
        for rank_idx, hit in enumerate(hits, start=1):
            cid = hit.chunk.id
            hit_map.setdefault(cid, hit)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + weight / (rrf_k + rank_idx)

    ordered = sorted(rrf_scores, key=lambda cid: (-rrf_scores[cid], str(cid)))
    return [replace(hit_map[cid], rank_score=rrf_scores[cid]) for cid in ordered[:top_k]]
