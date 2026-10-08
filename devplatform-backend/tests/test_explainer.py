import json

from app.services.explainer import Explainer
from app.services.llm import FakeLLM
from app.services.retrieval import Hit


def hit(i, sim, name="enforce_rate_limit", content="def enforce_rate_limit(r): ...", path="api/rl.py"):
    return Hit(i, path, 10, 20, name, "function", "python", "code", None, content, sim, sim)


class Scripted:
    def __init__(self, out):
        self.out, self.calls = out, 0

    def complete(self, system, user, max_tokens=1024):
        self.calls += 1
        return self.out if isinstance(self.out, str) else json.dumps(self.out)


def make(hits, llm, **kw):
    return Explainer(lambda q, k: hits, llm, min_similarity=0.3, **kw)


def test_confident_answer_has_valid_citations():
    r = make([hit(1, 0.8), hit(2, 0.5, name="other")], FakeLLM()).explain("where is rate limiting")
    assert not r.low_confidence and [i for i, _ in r.citations] == [1]
    assert r.citations[0][1].file_path == "api/rl.py" and r.citations[0][1].start_line == 10
    assert [h.chunk_id for h in r.related] == [2]


def test_low_similarity_skips_llm_entirely():
    llm = Scripted({})
    r = make([hit(1, 0.1)], llm).explain("unrelated question")
    assert r.low_confidence and r.reason == "retrieval_below_threshold" and llm.calls == 0


def test_model_says_insufficient():
    r = make([hit(1, 0.8)], Scripted({"answer": "?", "citations": [], "sufficient": False})).explain("q")
    assert r.low_confidence and r.reason == "model_reported_insufficient_context"


def test_invalid_citation_markers_are_stripped_and_can_force_low_confidence():
    ok = make([hit(1, 0.8)], Scripted({"answer": "Uses `enforce_rate_limit` [1][7].", "citations": [1, 7],
                                       "sufficient": True})).explain("q")
    assert not ok.low_confidence and "[7]" not in ok.answer
    bad = make([hit(1, 0.8)], Scripted({"answer": "Does a thing [9].", "citations": [9],
                                        "sufficient": True})).explain("q")
    assert bad.low_confidence and bad.reason == "no_valid_citations"


def test_ungrounded_identifiers_flagged():
    out = {"answer": "It calls `fake_one` and `fake_two` [1].", "citations": [1], "sufficient": True}
    r = make([hit(1, 0.8)], Scripted(out)).explain("q")
    assert r.low_confidence and r.reason == "ungrounded_identifiers"


def test_json_in_code_fence_is_parsed():
    raw = '```json\n{"answer": "Yes `enforce_rate_limit` [1]", "citations": [1], "sufficient": true}\n```'
    assert not make([hit(1, 0.8)], Scripted(raw)).explain("q").low_confidence
    assert make([hit(1, 0.8)], Scripted("not json")).explain("q").reason == "unparseable_llm_output"
