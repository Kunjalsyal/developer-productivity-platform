from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..connectors.github import GitHubConnector
from ..db import get_db
from ..deps import embedder_dep, github_dep, llm_dep, require_repo
from ..models import PRSummary, Repository
from ..schemas import PRListItem, PRSummaryOut
from ..services.pr_summary import summarize_pr

router = APIRouter(prefix="/repositories/{repo_id}/pulls", tags=["pull requests"])


@router.get("", response_model=list[PRListItem])
def list_open_prs(repo: Repository = Depends(require_repo), db: Session = Depends(get_db),
                  gh: GitHubConnector = Depends(github_dep)):
    done = set(db.scalars(select(PRSummary.pr_number).where(PRSummary.repository_id == repo.id)))
    return [PRListItem(number=p["number"], title=p["title"], author=(p.get("user") or {}).get("login"),
                       url=p["html_url"], updated_at=p["updated_at"], summarized=p["number"] in done)
            for p in gh.list_open_prs(repo.owner, repo.name)]


@router.post("/{number}/summary", response_model=PRSummaryOut)
def summarize(number: int, force: bool = False, repo: Repository = Depends(require_repo),
              db: Session = Depends(get_db), gh: GitHubConnector = Depends(github_dep),
              llm=Depends(llm_dep), embedder=Depends(embedder_dep)):
    row, cached = summarize_pr(db, repo, number, gh, llm, embedder, force)
    out = PRSummaryOut.model_validate(row)
    out.cached = cached
    return out
