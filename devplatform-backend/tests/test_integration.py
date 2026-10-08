"""Needs Postgres with pgvector: set TEST_DATABASE_URL (CI does this)."""
import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

FILES = {
    "api/middleware/rate_limit.py": (
        "from api.auth.tokens import verify_jwt\n\n\n"
        "def enforce_rate_limit(request):\n"
        "    key = verify_jwt(request.token)\n"
        "    if bucket(key).tokens < 1:\n"
        "        raise HTTPError(429, 'rate limit exceeded')\n"),
    "api/auth/tokens.py": "def verify_jwt(token):\n    return decode(token)\n",
    "api/payments/refunds.py": "def process_refund(charge_id):\n    return reverse(charge_id)\n",
    "web/src/App.tsx": "import { x } from './util';\nexport const App = () => x;\n",
    "web/src/util.ts": "export const x = 1;\n",
}


def test_index_search_explain_graph():
    from app.connectors.base import SourceDocument
    from app.db import SessionLocal, init_db
    from app.models import Repository
    from app.services import retrieval
    from app.services.embeddings import get_embedder
    from app.services.explainer import Explainer
    from app.services.graph import build_graph
    from app.services.indexer import Indexer
    from app.services.llm import FakeLLM

    init_db()
    db = SessionLocal()
    repo = Repository(url="https://github.com/acme/it-test", owner="acme", name="it-test")
    db.add(repo)
    db.commit()
    try:
        docs = [SourceDocument(p, c, "code") for p, c in FILES.items()]
        stats = Indexer(db, get_embedder()).index_documents(repo.id, docs, {"code"})
        assert stats.files == 5 and stats.chunks >= 5

        hits = retrieval.search(db, repo.id, "where is rate limiting enforced", get_embedder(), top_k=3)
        assert hits[0].name == "enforce_rate_limit"
        assert (hits[0].start_line, hits[0].end_line) == (4, 7)

        ex = Explainer(lambda q, k: retrieval.search(db, repo.id, q, get_embedder(), k), FakeLLM(),
                       min_similarity=0.05)
        r = ex.explain("where is rate limiting enforced")
        assert not r.low_confidence and r.citations[0][1].file_path == "api/middleware/rate_limit.py"

        g = build_graph(db, repo.id)
        edges = {(e["source"], e["target"]) for e in g["edges"]}
        assert ("api/middleware/rate_limit.py", "api/auth/tokens.py") in edges
        assert ("web/src/App.tsx", "web/src/util.ts") in edges
    finally:
        db.delete(db.get(Repository, repo.id))
        db.commit()
        db.close()
