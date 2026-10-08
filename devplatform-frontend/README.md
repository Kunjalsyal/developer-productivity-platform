# Developer Productivity Platform — Frontend

React + TypeScript + Vite + Tailwind CSS single-page app for the [backend](../devplatform-backend):
connect a GitHub repo, search code by intent, get cited answers (or an honest "low confidence"),
summarize pull requests, and explore the import graph with React Flow.

| Page | What it does | Backend endpoint |
|---|---|---|
| Dashboard | Connect / re-index / delete repos, live indexing status | `/api/repositories` |
| Code search | Semantic search with line-numbered code and citations | `POST .../search` |
| Explainer | Cited answers; refusal card with the reason when unsupported | `POST .../explain` |
| Pull requests | Open PRs, plain-language summaries with linked discussion | `.../pulls` |
| Architecture | File dependency graph (React Flow) | `GET .../graph` |

## Run

```bash
# 1. start the backend first (docker compose up --build, in the backend folder)
npm install
cp .env.example .env     # Windows: copy .env.example .env
npm run dev              # http://localhost:5173
```

`VITE_API_URL` points at the backend (default `http://localhost:8000`). If you enabled `API_KEY` on the backend,
set `VITE_API_KEY` too. Anything in a `VITE_` variable ships to the browser, so that is for demos only.
A GitHub token typed on the Dashboard stays in the browser tab's session storage and is sent as a header, never saved.

## Notes
- Server state is polled every 3 s while a repo is indexing.
- Colours follow the OS light/dark setting.
- `npm run build` type-checks and builds; CI runs it on every push.
