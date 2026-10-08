"""Dense vector search over persisted chunks (FR-08)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
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
    """Cosine similarity in [-1, 1]; vectors are normalized so this equals the dot product."""


def search_chunks(
    session: Session,
    query_vector: list[float],
    top_k: int,
    paper_ids: list[uuid.UUID] | None = None,
) -> list[ChunkHit]:
    # HNSW returns at most ef_search candidates, and filters are applied after the index scan; raise
    # ef_search and enable pgvector's iterative scan so filtered queries still return up to top_k
    # results in exact distance order. set_config(..., is_local => true) is the parameterizable
    # equivalent of SET LOCAL.
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
