
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..connectors.github import parse_repo_url
from ..db import get_db
from ..deps import require_repo
from ..models import Repository
from ..schemas import RepoCreate, RepoOut
from ..services.jobs import run_index_job

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.post("", response_model=RepoOut, status_code=202)
def connect_repository(body: RepoCreate, background: BackgroundTasks, db: Session = Depends(get_db),
                       x_github_token: str | None = Header(None), x_notion_token: str | None = Header(None)):
    """Connect a GitHub repo (and optionally Notion) and start indexing in the background."""
    s = get_settings()
    if body.include_notion and not (x_notion_token or s.notion_token):
        raise HTTPException(400, "include_notion requires NOTION_TOKEN or an X-Notion-Token header")
    owner, name = parse_repo_url(body.url)
    url = f"https://github.com/{owner}/{name}"
    existing = db.scalar(select(Repository).where(Repository.url == url))
    if existing:
        raise HTTPException(409, f"already connected: {existing.id}")
    repo = Repository(url=url, owner=owner, name=name, branch=body.branch, include_notion=body.include_notion,
                      notion_root_id=body.notion_root_id, index_status="pending")
    db.add(repo)
    db.commit()
    background.add_task(run_index_job, repo.id, x_github_token, x_notion_token)
    return repo


@router.get("", response_model=list[RepoOut])
def list_repositories(db: Session = Depends(get_db)):
    return db.scalars(select(Repository).order_by(Repository.created_at.desc())).all()


@router.get("/{repo_id}", response_model=RepoOut)
def get_repository(repo: Repository = Depends(require_repo)):
    return repo


@router.post("/{repo_id}/reindex", response_model=RepoOut, status_code=202)
def reindex(background: BackgroundTasks, repo: Repository = Depends(require_repo), db: Session = Depends(get_db),
            x_github_token: str | None = Header(None), x_notion_token: str | None = Header(None)):
    if repo.index_status == "indexing":
        raise HTTPException(409, "indexing already in progress")
    repo.index_status = "pending"
    db.commit()
    background.add_task(run_index_job, repo.id, x_github_token, x_notion_token)
    return repo


@router.delete("/{repo_id}", status_code=204)
def delete_repository(repo: Repository = Depends(require_repo), db: Session = Depends(get_db)):
    db.delete(repo)  # chunks / edges / summaries go via ON DELETE CASCADE
    db.commit()
