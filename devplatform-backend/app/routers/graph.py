from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_ready
from ..models import Repository
from ..schemas import GraphOut
from ..services.graph import build_graph

router = APIRouter(prefix="/repositories/{repo_id}", tags=["architecture"])


@router.get("/graph", response_model=GraphOut)
def dependency_graph(repo: Repository = Depends(require_ready), db: Session = Depends(get_db)):
    """File-level import graph shaped for React Flow (nodes + edges)."""
    return build_graph(db, repo.id)
