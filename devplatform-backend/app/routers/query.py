import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import embedder_dep, llm_dep, require_ready
from ..models import Repository
from ..schemas import CitationOut, ExplainRequest, ExplainResponse, SearchHit, SearchRequest, SearchResponse
from ..services import retrieval
from ..services.explainer import Explainer

router = APIRouter(prefix="/repositories/{repo_id}", tags=["query"])


def _hit(h: retrieval.Hit) -> dict:
    return dict(chunk_id=h.chunk_id, file_path=h.file_path, start_line=h.start_line, end_line=h.end_line,
                name=h.name, kind=h.kind, language=h.language, source=h.source, url=h.url,
                similarity=round(h.similarity, 4), score=round(h.score, 4), content=h.content)


@router.post("/search", response_model=SearchResponse)
def semantic_search(body: SearchRequest, repo: Repository = Depends(require_ready),
                    db: Session = Depends(get_db), embedder=Depends(embedder_dep)):
    t0 = time.perf_counter()
    hits = retrieval.search(db, repo.id, body.query, embedder, body.top_k, body.sources, body.languages)
    return SearchResponse(results=[SearchHit(**_hit(h)) for h in hits],
                          latency_ms=int((time.perf_counter() - t0) * 1000))


@router.post("/explain", response_model=ExplainResponse)
def explain(body: ExplainRequest, repo: Repository = Depends(require_ready), db: Session = Depends(get_db),
            embedder=Depends(embedder_dep), llm=Depends(llm_dep)):
    s = get_settings()
    t0 = time.perf_counter()
    ex = Explainer(lambda q, k: retrieval.search(db, repo.id, q, embedder, k), llm,
                   min_similarity=s.min_similarity, min_supporting=s.min_supporting_chunks,
                   max_context=s.max_context_chunks, top_k=s.top_k, max_tokens=s.llm_max_tokens)
    r = ex.explain(body.query)
    return ExplainResponse(
        answer=r.answer, low_confidence=r.low_confidence, reason=r.reason, confidence=round(r.confidence, 4),
        citations=[CitationOut(index=i, **_hit(h)) for i, h in r.citations],
        related=[CitationOut(**_hit(h)) for h in r.related],
        unverified_terms=r.unverified_terms, latency_ms=int((time.perf_counter() - t0) * 1000))
