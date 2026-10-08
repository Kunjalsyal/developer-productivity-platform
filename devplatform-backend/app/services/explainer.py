"""Citation-grounded RAG explainer with a low-confidence gate (report Objective 3)."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from .llm import LLMClient
from .retrieval import Hit

SYSTEM = """You answer questions about a software repository using ONLY the numbered context blocks provided.
Rules:
- Every factual claim must be followed by a citation like [1] or [2][3] referring to a context block.
- Never mention code, files or behaviour that is not in the context.
- If the context does not contain enough information to answer, set "sufficient" to false.
- Wrap identifiers in backticks.
Respond with one JSON object and nothing else:
{"answer": "<text with [n] citations>", "citations": [<block numbers used>], "sufficient": true|false}"""

LOW_CONF_TEXT = "I couldn't find enough support in the indexed repository to answer this reliably."


@dataclass
class ExplainResult:
    answer: str
    low_confidence: bool
    reason: str | None
    confidence: float
    citations: list[tuple[int, Hit]] = field(default_factory=list)
    related: list[Hit] = field(default_factory=list)
    unverified_terms: list[str] = field(default_factory=list)


def parse_json(raw: str):
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _grounded(ident: str, corpus: str) -> bool:
    if ident in corpus:
        return True
    return "/" not in ident and "." in ident and ident.split(".")[-1] in corpus


class Explainer:
    def __init__(self, search_fn: Callable[[str, int], list[Hit]], llm: LLMClient, *,
                 min_similarity: float = 0.30, min_supporting: int = 1, max_context: int = 6,
                 top_k: int = 8, max_tokens: int = 1024):
        self.search_fn, self.llm = search_fn, llm
        self.min_similarity, self.min_supporting = min_similarity, min_supporting
        self.max_context, self.top_k, self.max_tokens = max_context, top_k, max_tokens

    @staticmethod
    def _prompt(query: str, ctx: list[Hit]) -> str:
        blocks = [f"[{i}] {h.file_path}:{h.start_line}-{h.end_line} ({h.kind} {h.name})\n```\n{h.content[:3000]}\n```"
                  for i, h in enumerate(ctx, 1)]
        return f"TASK: CODE_QUESTION\nQuestion: {query}\n\nContext:\n" + "\n\n".join(blocks)

    @staticmethod
    def _low(hits: list[Hit], reason: str) -> ExplainResult:
        return ExplainResult(LOW_CONF_TEXT, True, reason, hits[0].similarity if hits else 0.0, [], hits[:3])

    def explain(self, query: str) -> ExplainResult:
        hits = self.search_fn(query, self.top_k)
        ctx = [h for h in hits if h.similarity >= self.min_similarity][: self.max_context]
        if len(ctx) < self.min_supporting:  # skip the LLM entirely: nothing relevant retrieved
            return self._low(hits, "retrieval_below_threshold")

        data = parse_json(self.llm.complete(SYSTEM, self._prompt(query, ctx), self.max_tokens))
        if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
            return self._low(hits, "unparseable_llm_output")
        if data.get("sufficient") is False:
            return self._low(hits, "model_reported_insufficient_context")

        answer = data["answer"].strip()
        claimed = {int(x) for x in data.get("citations", []) if str(x).isdigit()}
        inline = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
        valid = {i for i in claimed | inline if 1 <= i <= len(ctx)}
        for bad in (claimed | inline) - valid:  # strip citations that point at nothing
            answer = answer.replace(f"[{bad}]", "")
        if not valid:
            return self._low(hits, "no_valid_citations")

        cited = [(i, ctx[i - 1]) for i in sorted(valid)]
        corpus = "\n".join(f"{h.file_path}\n{h.name}\n{h.content}" for h in ctx)
        idents = list(dict.fromkeys(re.findall(r"`([A-Za-z_][\w./:-]*)(?:\(\))?`", answer)))
        unverified = [i for i in idents if not _grounded(i, corpus)]
        if len(unverified) >= 2 and len(unverified) / len(idents) > 0.5:
            return self._low(hits, "ungrounded_identifiers")

        cited_ids = {h.chunk_id for _, h in cited}
        return ExplainResult(
            answer=answer, low_confidence=False, reason=None,
            confidence=sum(h.similarity for _, h in cited) / len(cited), citations=cited,
            related=[h for h in hits if h.chunk_id not in cited_ids][:3], unverified_terms=unverified)
