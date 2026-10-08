# Developer Productivity Platform

A developer tool for exploring and understanding large GitHub repositories through code search, repository analysis, pull request summaries, and architecture visualization.

## Live Demo

**Frontend:** https://devplatform-web-uhpw.onrender.com/

The deployed application connects a React frontend to a FastAPI backend and PostgreSQL database with pgvector.

> The deployed demo uses a lightweight retrieval configuration to operate within free hosting resource limits. The full Sentence Transformer and LLM configuration is available in the local development setup.

## Features

### Repository Integration

* Connect GitHub repositories directly to the platform
* Import repository source code
* Track repository indexing status
* Re-index repositories when the code changes

### Code Search

* Search across the indexed repository
* Retrieve relevant code sections based on a query
* Display file paths and source context for retrieved results

### Code Explainer

* Explain repository code and implementation details
* Retrieve supporting code context before generating an explanation
* Provide source citations for retrieved code
* Return low-confidence results when sufficient supporting context is not available

### Pull Request Analysis

* Retrieve open pull requests from GitHub
* Generate summaries of pull request changes
* Display relevant repository and change information

### Architecture View

* Analyze imports between source files
* Build a repository-level dependency graph
* Visualize relationships between files and modules

## Architecture

```text
                    ┌──────────────────────┐
                    │      React + Vite    │
                    │      Frontend        │
                    └──────────┬───────────┘
                               │
                               │ REST API
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI        │
                    │       Backend        │
                    └───────┬───────┬──────┘
                            │       │
                ┌───────────┘       └────────────┐
                ▼                                ▼
       ┌─────────────────┐              ┌─────────────────┐
       │ PostgreSQL      │              │ GitHub API      │
       │ + pgvector      │              │                 │
       └─────────────────┘              └─────────────────┘
                │
                ▼
       ┌─────────────────┐
       │ Retrieval &     │
       │ Embeddings      │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │ LLM Provider    │
       └─────────────────┘
```

## Tech Stack

### Frontend

* React
* TypeScript
* Vite
* Tailwind CSS

### Backend

* Python
* FastAPI
* SQLAlchemy
* Pydantic

### Database

* PostgreSQL
* pgvector

### Integrations

* GitHub API
* Notion API

### AI / Retrieval

* Sentence Transformers
* Vector embeddings
* pgvector similarity search
* Configurable LLM providers

## Repository Structure

```text
developer-productivity-platform/
│
├── devplatform-backend/
│   ├── app/
│   │   ├── connectors/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models.py
│   │   └── main.py
│   ├── tests/
│   ├── eval/
│   ├── scripts/
│   ├── requirements-core.txt
│   └── Dockerfile
│
└── devplatform-frontend/
    ├── src/
    │   ├── components/
    │   ├── pages/
    │   ├── state/
    │   ├── api.ts
    │   └── App.tsx
    ├── package.json
    └── vite.config.ts
```

## Local Development

### Backend

```bash
cd devplatform-backend

python -m venv .venv
```

Activate the virtual environment.

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements-core.txt
```

Create a `.env` file using `.env.example` and configure PostgreSQL.

Start the backend:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

### Frontend

```bash
cd devplatform-frontend
npm install
npm run dev
```

The frontend will be available at:

```text
http://localhost:5173
```

## Configuration

The application supports configurable:

* PostgreSQL connection
* GitHub authentication
* Notion integration
* Embedding backend
* Embedding model
* LLM provider
* API authentication
* CORS origins
* Retrieval parameters

Example environment configuration:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/devplatform

EMBEDDING_BACKEND=sentence-transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

LLM_PROVIDER=groq
GROQ_API_KEY=your_api_key
```

## Testing

Run the backend test suite with:

```bash
pytest
```

The project includes tests covering API routes, database integration, chunking, embeddings, retrieval, graph generation, and indexing workflows.

## Deployment

The application is deployed using:

* Render Static Site for the frontend
* Render Web Service for the backend
* Render PostgreSQL with pgvector

The frontend communicates with the deployed FastAPI backend through the configured API URL.

## Design Considerations

The platform separates repository ingestion, chunking, embedding, retrieval, and response generation into independent services. This makes the retrieval pipeline easier to test and allows the embedding and LLM providers to be changed without modifying the core application.

The system also uses confidence checks before generating explanations. When retrieved context does not provide enough supporting evidence, the system returns a low-confidence response rather than relying on unsupported information.

## Future Improvements

* Background job queue using Celery or RQ
* Persistent database migrations using Alembic
* Improved production authentication
* Incremental repository indexing
* More advanced code-aware retrieval
* Additional GitHub workflow integrations
