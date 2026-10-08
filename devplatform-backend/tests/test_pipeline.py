"""End-to-end index job + PR summary against a mocked GitHub API (needs TEST_DATABASE_URL)."""
import io
import os
import tarfile

import httpx
import pytest

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

REPO_FILES = {
    "api/rate_limit.py": "def enforce_rate_limit(req):\n    return req.count < 100\n",
    "api/main.py": (
        "from api.rate_limit import enforce_rate_limit\n\n\n"
        "def handle(req):\n    return enforce_rate_limit(req)\n"),
    "README.md": "# Demo\nA tiny API.\n",
    "node_modules/x/index.js": "ignored()",
    "logo.png": "binary",
}
DIFF = ("diff --git a/api/rate_limit.py b/api/rate_limit.py\n--- a/api/rate_limit.py\n+++ b/api/rate_limit.py\n"
        "@@ -1,2 +1,2 @@\n def enforce_rate_limit(req):\n-    return req.count < 50\n+    return req.count < 100\n")


def tarball() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, text in REPO_FILES.items():
            data = text.encode()
            info = tarfile.TarInfo(f"acme-demo-abc123/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def handler(request: httpx.Request) -> httpx.Response:
    p, accept = request.url.path, request.headers.get("accept", "")
    if p.endswith("/tarball/main"):
        return httpx.Response(200, content=tarball())
    if p.endswith("/commits/main"):
        return httpx.Response(200, text="abc123")
    if p == "/repos/acme/demo":
        return httpx.Response(200, json={"default_branch": "main"})
    if p == "/repos/acme/demo/pulls/7":
        if "diff" in accept:
            return httpx.Response(200, text=DIFF)
        return httpx.Response(200, json={"number": 7, "title": "Raise rate limit to 100", "head": {"sha": "h1"},
                                         "body": "Fixes #3", "user": {"login": "k"}, "html_url": "http://pr/7"})
    if p == "/repos/acme/demo/issues/3":
        return httpx.Response(200, json={"title": "Users get throttled", "body": "too strict",
                                         "user": {"login": "u"}, "html_url": "http://i/3"})
    if p.endswith("/comments"):
        return httpx.Response(200, json=[])
    return httpx.Response(404)


def mock_gh(token=None):
    from app.connectors.github import GitHubConnector
    return GitHubConnector(token, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_index_job_then_pr_summary(monkeypatch):
    from sqlalchemy import select

    from app.db import SessionLocal, init_db
    from app.models import Chunk, Repository
    from app.services import jobs
    from app.services.embeddings import get_embedder
    from app.services.llm import FakeLLM
    from app.services.pr_summary import summarize_pr

    init_db()
    monkeypatch.setattr(jobs, "GitHubConnector", mock_gh)
    db = SessionLocal()
    repo = Repository(url="https://github.com/acme/demo", owner="acme", name="demo")
    db.add(repo)
    db.commit()
    try:
        jobs.run_index_job(repo.id)
        db.refresh(repo)
        assert repo.index_status == "ready", repo.index_error
        assert repo.commit_sha == "abc123" and repo.branch == "main"
        paths = set(db.scalars(select(Chunk.file_path).where(Chunk.repository_id == repo.id)))
        assert paths == {"api/rate_limit.py", "api/main.py", "README.md"}  # node_modules + png skipped

        row, cached = summarize_pr(db, repo, 7, mock_gh(), FakeLLM(), get_embedder())
        assert not cached and "Raise rate limit" in row.summary
        assert row.related["changed_files"] == ["api/rate_limit.py"]
        assert any(d["kind"] == "issue" and d["ref"] == "#3" for d in row.related["discussion"])
        _, cached2 = summarize_pr(db, repo, 7, mock_gh(), FakeLLM(), get_embedder())
        assert cached2
    finally:
        db.delete(db.get(Repository, repo.id))
        db.commit()
        db.close()
