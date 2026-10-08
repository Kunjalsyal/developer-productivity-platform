import hmac
import uuid
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .config import get_settings
from .connectors.github import GitHubConnector
from .db import get_db
from .models import Repository
from .services.embeddings import Embedder, get_embedder
from .services.llm import LLMClient, get_llm


def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    key = get_settings().api_key
    if key and not hmac.compare_digest(x_api_key or "", key):
        raise HTTPException(401, "invalid or missing X-API-Key")


def embedder_dep() -> Embedder:
    return get_embedder()


def llm_dep() -> LLMClient:
    return get_llm()


def github_dep(x_github_token: str | None = Header(None)) -> Iterator[GitHubConnector]:
    gh = GitHubConnector(x_github_token or get_settings().github_token)
    try:
        yield gh
    finally:
        gh.close()


def require_repo(repo_id: uuid.UUID, db: Session = Depends(get_db)) -> Repository:
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "repository not found")
    return repo


def require_ready(repo: Repository = Depends(require_repo)) -> Repository:
    if repo.index_status != "ready":
        raise HTTPException(409, f"repository is not ready (status: {repo.index_status})")
    return repo
