from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .connectors.base import ConnectorError
from .db import get_db, init_db
from .deps import verify_api_key
from .routers import graph, pulls, query, repos


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_create_schema:
        init_db()
    yield


app = FastAPI(title="Developer Productivity Platform API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["*"],
                   allow_headers=["*"])


@app.exception_handler(ConnectorError)
async def connector_error(_: Request, exc: ConnectorError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "upstream_status": exc.status})


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["meta"])
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


for r in (repos.router, query.router, pulls.router, graph.router):
    app.include_router(r, prefix="/api", dependencies=[Depends(verify_api_key)])
