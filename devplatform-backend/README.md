# Developer Productivity Platform — Backend

FastAPI + PostgreSQL/pgvector backend for an AI-assisted codebase intelligence tool:
AST-based indexing (tree-sitter), semantic code search, a citation-grounded explainer that flags
low-confidence answers instead of fabricating, GitHub + Notion connectors, PR summaries, and a
dependency graph for the React Flow viewer.

```
React SPA ──REST/JSON──> FastAPI ──> PostgreSQL + pgvector (metadata + embeddings)
                           ├──> GitHub API (code tarball, PRs, issues, comments)
                           ├──> Notion API (docs)
                           └──> LLM (Anthropic | OpenAI | fake), provider-configurable
```

## Quick start

```bash
cp .env.example .env            # set ANTHROPIC_API_KEY (or LLM_PROVIDER=openai/fake) and GITHUB_TOKEN
docker compose up --build       # API on :8000, docs at http://localhost:8000/docs
```

Without Docker: start Postgres with pgvector (`docker run -p 5432:5432 -e POSTGRES_PASSWORD=postgres
-e POSTGRES_DB=devplatform pgvector/pgvector:pg16`), then
`pip install -r requirements.txt && uvicorn app.main:app --reload`.
Tables and the `vector` extension are created on startup (`AUTO_CREATE_SCHEMA`).

```bash
# 1. connect + index (returns 202; poll GET /api/repositories/{id} until index_status == "ready")
curl -X POST localhost:8000/api/repositories -H 'content-type: application/json' \
     -d '{"url":"https://github.com/owner/repo"}'
# 2. search by intent
curl -X POST localhost:8000/api/repositories/$ID/search -H 'content-type: application/json' \
     -d '{"query":"where is rate limiting enforced","top_k":5}'
# 3. cited answer (or low_confidence=true)
curl -X POST localhost:8000/api/repositories/$ID/explain -H 'content-type: application/json' \
     -d '{"query":"how are failed payments retried?"}'
```

## API (all under `/api`; `X-API-Key` required if `API_KEY` is set)

| Method & path | Purpose |
|---|---|
| `POST /repositories` | Connect GitHub repo (`include_notion`, `notion_root_id`, `branch` optional) and index in background |
| `GET /repositories`, `GET /repositories/{id}` | List / status (`pending → indexing → ready \| failed`) |
| `POST /repositories/{id}/reindex`, `DELETE /repositories/{id}` | Re-index / remove everything |
| `POST /repositories/{id}/search` | Semantic search → ranked chunks with `file_path:start_line-end_line` |
| `POST /repositories/{id}/explain` | RAG answer with `[n]` citations, `confidence`, `low_confidence` + `reason` |
| `GET /repositories/{id}/pulls` | Open PRs (+ whether summarized) |
| `POST /repositories/{id}/pulls/{n}/summary` | Plain-language summary + linked discussion/docs/files (`?force=true` to redo) |
| `GET /repositories/{id}/graph` | `{nodes, edges}` file-level import graph for React Flow |
| `GET /health`, `GET /ready` | Liveness / DB check |

Private repos: set `GITHUB_TOKEN`, or send `X-GitHub-Token` (and `X-Notion-Token`) per request; tokens are never stored.

## How it works

- **Chunking** (`services/chunker.py`): tree-sitter splits Python/JS/TS into functions, classes (header only) and methods, with exact 1-based line ranges; Markdown/Notion text is split on headings. Chunks over `MAX_CHUNK_CHARS` are split into line windows.
- **Embeddings**: `sentence-transformers` (default `all-MiniLM-L6-v2`, 384-d, normalized). `EMBEDDING_BACKEND=hash` is a lexical stand-in for tests/offline dev only. Changing the model's dimension means changing `EMBEDDING_DIM` and recreating the `chunks` table.
- **Retrieval**: pgvector HNSW index, cosine distance, plus a small boost when query words match the symbol name.
- **Explainer** (`services/explainer.py`) is low-confidence when any of these hold: too few chunks above `MIN_SIMILARITY` (the LLM is not even called), the model says the context is insufficient, no valid `[n]` citation survives validation, or most backticked identifiers in the answer don't appear in the retrieved code. Invalid citation markers are stripped.
- **Graph**: import statements are resolved to indexed files (Python absolute/relative, JS/TS relative, `@/` alias); packages and stdlib are treated as external.

## Measuring the report's targets

`scripts/eval_search.py` computes precision@5, search/explainer latency, low-confidence rate, and citation accuracy
(compares each cited line range with a local checkout at the same commit). Write ~20 hand-labelled queries like
`eval/queries.example.json`, run it, then tune `MIN_SIMILARITY` (default 0.30 is a starting guess for MiniLM, not a calibrated value).

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                   # unit tests, no services needed
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/devplatform_test pytest   # + DB tests
```
CI (`.github/workflows/ci.yml`) runs everything against a `pgvector/pgvector:pg16` service.

## Known limitations

- Indexing runs in FastAPI background tasks (in-process); use a job queue (RQ/Celery) for multi-worker production.
- Schema is created with `create_all`; add Alembic before you need migrations.
- Languages: Python, JavaScript, TypeScript/TSX. Only the default branch (or `branch`) is indexed; no incremental re-index yet.
- GitHub tarball download is capped by `MAX_FILE_BYTES` per file but not by repo size.
