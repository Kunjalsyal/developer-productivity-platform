"""Plain-language PR summaries linked to related discussion, docs and code."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors.github import GitHubConnector
from ..models import Chunk, PRSummary, Repository
from . import retrieval
from .embeddings import Embedder
from .explainer import parse_json
from .llm import LLMClient

SYSTEM = """You explain pull requests to a teammate who has not seen the code.
Write plain language, no jargon you cannot justify from the input. Use the discussion ONLY for the
'why'; if it does not say why, say so instead of guessing. Respond with one JSON object and nothing else:
{"summary": "<2-4 sentences: what changed>", "why": "<motivation from the discussion, or 'Not stated.'>",
 "review_notes": ["<things a reviewer should check>", ...]}"""


def condense_diff(diff: str, budget: int = 24000, per_file: int = 3000) -> tuple[str, list[str]]:
    parts = [p for p in re.split(r"(?m)^(?=diff --git )", diff) if p.strip()]
    files = [m.group(1) for p in parts if (m := re.match(r"diff --git a/(.+?) b/", p))]
    out, used = [], 0
    for p in parts:
        p = p[:per_file] + ("\n...[truncated]" if len(p) > per_file else "")
        if used + len(p) > budget:
            p = p.split("\n", 1)[0] + "\n...[omitted: diff budget reached]"
        out.append(p)
        used += len(p)
    return "\n".join(out), files


def summarize_pr(db: Session, repo: Repository, number: int, gh: GitHubConnector, llm: LLMClient,
                 embedder: Embedder, force: bool = False) -> tuple[PRSummary, bool]:
    pr = gh.get_pr(repo.owner, repo.name, number)
    sha = pr["head"]["sha"]
    cached = db.scalar(select(PRSummary).where(
        PRSummary.repository_id == repo.id, PRSummary.pr_number == number, PRSummary.head_sha == sha))
    if cached and not force:
        return cached, True

    diff, files = condense_diff(gh.get_pr_diff(repo.owner, repo.name, number))
    discussion = gh.get_pr_discussion(repo.owner, repo.name, pr)
    docs = retrieval.search(db, repo.id, f"{pr['title']}\n{(pr.get('body') or '')[:500]}", embedder,
                            top_k=3, sources=["notion", "doc"])
    touched = db.execute(select(Chunk.file_path, Chunk.name).where(
        Chunk.repository_id == repo.id, Chunk.source == "code", Chunk.file_path.in_(files)).limit(40)).all()

    prompt = (
        f"TASK: PR_SUMMARY\nTitle: {pr['title']}\n\n"
        f"Description:\n{(pr.get('body') or '(none)')[:2000]}\n\n"
        f"Discussion:\n" + "\n".join(f"- ({d.kind} {d.ref}) {d.text[:600]}" for d in discussion[:15]) + "\n\n"
        "Existing symbols in touched files:\n" + ", ".join(f"{p}::{n}" for p, n in touched) + "\n\n"
        f"Diff:\n{diff}")
    data = parse_json(llm.complete(SYSTEM, prompt, 1024)) or {}

    related = {
        "changed_files": files,
        "discussion": [{"kind": d.kind, "ref": d.ref, "author": d.author, "url": d.url, "excerpt": d.text[:300]}
                       for d in discussion],
        "docs": [{"title": h.name, "path": h.file_path, "url": h.url, "similarity": round(h.similarity, 3)}
                 for h in docs],
    }
    row = cached or PRSummary(repository_id=repo.id, pr_number=number, head_sha=sha)
    row.title, row.url = pr["title"], pr.get("html_url")
    row.summary = data.get("summary") or "Summary unavailable: the model returned no usable output."
    row.why = data.get("why") or "Not stated."
    row.review_notes, row.related = list(data.get("review_notes") or []), related
    db.add(row)
    db.commit()
    return row, False
