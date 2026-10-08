from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Chunk
from .embeddings import Embedder, code_tokens

_STOP = {"the", "a", "an", "is", "are", "of", "in", "to", "for", "where", "how", "what", "does", "do",
         "and", "or", "it", "this", "that", "why", "when", "which", "with", "by", "on"}


@dataclass
class Hit:
    chunk_id: int
    file_path: str
    start_line: int
    end_line: int
    name: str
    kind: str
    language: str | None
    source: str
    url: str | None
    content: str
    similarity: float  # raw cosine similarity (used for confidence gating)
    score: float  # similarity + small symbol-name boost (used for ranking)


def search(db: Session, repo_id: uuid.UUID, query: str, embedder: Embedder, top_k: int = 8,
           sources: list[str] | None = None, languages: list[str] | None = None) -> list[Hit]:
    qvec = embedder.embed([query])[0]
    dist = Chunk.embedding.cosine_distance(qvec).label("distance")
    stmt = select(Chunk, dist).where(Chunk.repository_id == repo_id)
    if sources:
        stmt = stmt.where(Chunk.source.in_(sources))
    if languages:
        stmt = stmt.where(Chunk.language.in_(languages))
    rows = db.execute(stmt.order_by(dist).limit(top_k * 3)).all()
    qtok = set(code_tokens(query)) - _STOP
    hits = []
    for c, d in rows:
        sim = 1.0 - float(d)
        boost = min(0.1, 0.05 * len(qtok & set(code_tokens(c.name))))
        hits.append(Hit(c.id, c.file_path, c.start_line, c.end_line, c.name, c.kind, c.language,
                        c.source, c.url, c.content, sim, sim + boost))
    hits.sort(key=lambda h: -h.score)
    return hits[:top_k]
