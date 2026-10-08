import logging
import uuid

from sqlalchemy import func, select

from ..config import get_settings
from ..connectors.github import GitHubConnector, RepoRef
from ..connectors.notion import NotionConnector
from ..db import SessionLocal
from ..models import Chunk, Repository, utcnow
from .embeddings import get_embedder
from .indexer import Indexer

log = logging.getLogger(__name__)


def run_index_job(repo_id: uuid.UUID, github_token: str | None = None, notion_token: str | None = None) -> None:
    """Background job: fetch from GitHub (and Notion), chunk, embed, store. Never raises."""
    s = get_settings()
    db = SessionLocal()
    gh = None
    try:
        repo = db.get(Repository, repo_id)
        repo.index_status, repo.index_error = "indexing", None
        db.commit()

        gh = GitHubConnector(github_token or s.github_token)
        branch = repo.branch or gh.get_repo(repo.owner, repo.name)["default_branch"]
        ref = RepoRef(repo.owner, repo.name, branch)
        docs = gh.fetch_context(ref)
        repo.commit_sha = gh.head_sha(repo.owner, repo.name, branch)

        indexer = Indexer(db, get_embedder())
        stats = indexer.index_documents(repo.id, docs, {"code", "doc"})
        files = stats.files

        if repo.include_notion:
            notion = NotionConnector(notion_token or s.notion_token, repo.notion_root_id)
            try:
                files += indexer.index_documents(repo.id, notion.fetch_context(repo), {"notion"}).files
            finally:
                notion.close()

        repo.file_count = files
        repo.chunk_count = db.scalar(select(func.count()).select_from(Chunk).where(Chunk.repository_id == repo.id))
        repo.branch, repo.index_status, repo.last_indexed_at = branch, "ready", utcnow()
        db.commit()
    except Exception as e:
        log.exception("index job failed for %s", repo_id)
        db.rollback()
        repo = db.get(Repository, repo_id)
        if repo:
            repo.index_status, repo.index_error = "failed", str(e)[:500]
            db.commit()
    finally:
        if gh:
            gh.close()
        db.close()
