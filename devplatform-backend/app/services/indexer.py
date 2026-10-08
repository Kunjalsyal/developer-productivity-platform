"""parse -> chunk -> embed -> store, for every document of a repository."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors.base import SourceDocument
from ..models import Chunk, ImportEdge
from .chunker import CodeChunk, chunk_text, detect_language, parse_file
from .embeddings import Embedder
from .graph import resolve_import

log = logging.getLogger(__name__)
BATCH = 64


@dataclass
class IndexStats:
    files: int = 0
    chunks: int = 0
    skipped: int = 0


def embedding_text(c: CodeChunk) -> str:
    return f"{c.kind} {c.name}\n{c.file_path}\n{c.content}"[:2000]


class Indexer:
    def __init__(self, db: Session, embedder: Embedder):
        self.db, self.embedder = db, embedder
        self.s = get_settings()

    def index_documents(self, repo_id: uuid.UUID, docs: list[SourceDocument], kinds: set[str]) -> IndexStats:
        """Replace everything of the given kinds ('code', 'doc', 'notion') with `docs`."""
        stats = IndexStats()
        self.db.execute(delete(Chunk).where(Chunk.repository_id == repo_id, Chunk.source.in_(kinds)))
        if "code" in kinds:
            self.db.execute(delete(ImportEdge).where(ImportEdge.repository_id == repo_id))

        rows: list[tuple[CodeChunk, str, str | None]] = []
        imports = []
        code_paths = {d.path for d in docs if d.kind == "code"}
        for d in docs:
            try:
                if d.kind == "code":
                    pf = parse_file(d.path, d.content, self.s.max_chunk_chars)
                    rows += [(c, "code", d.url) for c in pf.chunks]
                    imports.append((d.path, detect_language(d.path), pf.imports))
                else:
                    cs = chunk_text(d.path, d.content, self.s.doc_chunk_chars, d.title)
                    rows += [(c, d.kind, d.url) for c in cs]
                stats.files += 1
            except Exception:  # one unparsable file must not fail the whole index
                log.exception("skipping %s", d.path)
                stats.skipped += 1

        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            vecs = self.embedder.embed([embedding_text(c) for c, _, _ in batch])
            self.db.add_all(
                Chunk(repository_id=repo_id, source=src, file_path=c.file_path, url=url,
                      start_line=c.start_line, end_line=c.end_line, name=c.name, kind=c.kind,
                      language=c.language, content=c.content, embedding=v)
                for (c, src, url), v in zip(batch, vecs))
            self.db.flush()
        stats.chunks = len(rows)

        for path, lang, refs in imports:
            seen = set()
            for ref in refs:
                targets = resolve_import(path, lang, ref, code_paths) or [None]
                for t in targets:
                    if (ref.raw, t) not in seen:
                        seen.add((ref.raw, t))
                        self.db.add(ImportEdge(repository_id=repo_id, source_path=path,
                                               target_module=ref.raw, target_path=t))
        self.db.commit()
        return stats
