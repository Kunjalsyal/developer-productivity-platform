"""HTTP-level test of search / explain / graph / lifecycle endpoints (needs TEST_DATABASE_URL)."""
import os

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")


def test_endpoints_roundtrip(monkeypatch):
    from app.config import get_settings
    from app.connectors.base import SourceDocument
    from app.db import SessionLocal, init_db
    from app.main import app
    from app.models import Repository
    from app.services.embeddings import get_embedder
    from app.services.indexer import Indexer

    monkeypatch.setattr(get_settings(), "min_similarity", 0.05)
    init_db()
    db = SessionLocal()
    repo = Repository(url="https://github.com/acme/api-test", owner="acme", name="api-test", index_status="pending")
    db.add(repo)
    db.commit()
    c = TestClient(app)
    base = f"/api/repositories/{repo.id}"
    try:
        assert c.post(f"{base}/search", json={"query": "rate limit"}).status_code == 409  # not ready yet
        Indexer(db, get_embedder()).index_documents(repo.id, [
            SourceDocument("a/limit.py", "def enforce_rate_limit(r):\n    return r\n", "code"),
            SourceDocument("a/use.py", "from a.limit import enforce_rate_limit\n\n\ndef go():\n    pass\n", "code"),
        ], {"code"})
        repo.index_status = "ready"
        db.commit()

        r = c.post(f"{base}/search", json={"query": "rate limit", "top_k": 2}).json()
        assert r["results"][0]["name"] == "enforce_rate_limit" and r["results"][0]["start_line"] == 1
        e = c.post(f"{base}/explain", json={"query": "where is rate limiting enforced"}).json()
        assert not e["low_confidence"] and e["citations"][0]["index"] == 1
        g = c.get(f"{base}/graph").json()
        assert {"id": "a/use.py->a/limit.py", "source": "a/use.py", "target": "a/limit.py"} in g["edges"]
        assert c.get(base).json()["id"] == str(repo.id)
        assert c.delete(base).status_code == 204
        assert c.get(base).status_code == 404
    finally:
        if db.get(Repository, repo.id):
            db.delete(db.get(Repository, repo.id))
            db.commit()
        db.close()
