"""Import resolution + dependency graph (feeds the React Flow architecture viewer)."""
from __future__ import annotations

import posixpath
import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Chunk, ImportEdge
from .chunker import ImportRef

_JS_SUFFIXES = ["", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
                "/index.ts", "/index.tsx", "/index.js", "/index.jsx"]


def resolve_python(source: str, ref: ImportRef, known: set[str]) -> list[str]:
    def join(*parts: str) -> str:
        return "/".join(p for p in parts if p)

    root = ""
    if ref.level:
        d = posixpath.dirname(source)
        for _ in range(ref.level - 1):
            d = posixpath.dirname(d)
        root = d
    mod = ref.module.replace(".", "/")
    bases = [join(root, mod)] if mod else []
    bases += [join(root, mod, n) for n in ref.names]
    found: list[str] = []
    for b in bases:
        for cand in (f"{b}.py", f"{b}/__init__.py"):
            if cand in known:
                found.append(cand)
            elif not ref.level:  # absolute import under a src/ layout
                matches = [k for k in known if k.endswith("/" + cand)]
                if len(matches) == 1:
                    found.append(matches[0])
    return [p for p in dict.fromkeys(found) if p != source]


def resolve_js(source: str, spec: str, known: set[str]) -> list[str]:
    if spec.startswith("."):
        base = posixpath.normpath(posixpath.join(posixpath.dirname(source), spec))
    elif spec.startswith(("@/", "~/")):
        base = "src/" + spec[2:]
    else:
        return []  # npm package
    bases = [base] + ([base.rsplit(".", 1)[0]] if base.endswith((".js", ".jsx")) else [])
    for b in bases:
        for suf in _JS_SUFFIXES:
            if b + suf in known and b + suf != source:
                return [b + suf]
    return []


def resolve_import(source: str, language: str, ref: ImportRef, known: set[str]) -> list[str]:
    return resolve_python(source, ref, known) if language == "python" else resolve_js(source, ref.module, known)


def build_graph(db: Session, repo_id: uuid.UUID) -> dict:
    counts = Counter()
    langs: dict[str, str] = {}
    rows = db.execute(
        select(Chunk.file_path, Chunk.language, func.count())
        .where(Chunk.repository_id == repo_id, Chunk.source == "code")
        .group_by(Chunk.file_path, Chunk.language)
    ).all()
    for path, lang, n in rows:
        counts[path] += n
        langs[path] = lang
    edges = db.execute(
        select(ImportEdge.source_path, ImportEdge.target_path)
        .where(ImportEdge.repository_id == repo_id, ImportEdge.target_path.is_not(None))
        .distinct()
    ).all()
    nodes = [
        {"id": p, "label": posixpath.basename(p), "group": p.split("/")[0] if "/" in p else "",
         "language": langs[p], "chunks": counts[p]}
        for p in sorted(counts)
    ]
    return {
        "nodes": nodes,
        "edges": [{"id": f"{s}->{t}", "source": s, "target": t} for s, t in edges if s in counts and t in counts],
    }
