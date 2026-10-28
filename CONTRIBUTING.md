# Contributing to GraphRAG Lab

Thanks for considering a contribution. This is a small portfolio-scale project
(FastAPI backend + React frontend + Neo4j), so the process is kept
lightweight — but PRs are genuinely reviewed and merged.

Looking for somewhere to start? Check issues labeled
[`good first issue`](https://github.com/iamvisheshsrivastava/graphrag-lab/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## Project layout

```
backend/   FastAPI app — routers/, services/, models/, tests/
frontend/  React (Vite) app — src/components/, src/lib/api.js
```

See the README's "Architecture" section for what each file does.

## Dev setup

### Backend (FastAPI + Neo4j)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # includes requirements.txt + pytest
cp .env.example .env
uvicorn main:app --reload --port 8000
```

- API docs (Swagger UI): http://localhost:8000/docs
- You do **not** need a real Neo4j instance or LLM API key to run the app or
  the test suite. Without `OPENROUTER_API_KEY`/`OPENAI_API_KEY` the graph
  builder falls back to deterministic keyword extraction; without
  `NEO4J_URI` the app just skips persistence (logged, non-fatal). This makes
  most of the backend fully testable offline.
- If you do want Neo4j locally, the quickest path is a free
  [Neo4j AuraDB](https://neo4j.com/cloud/aura/) instance — paste its
  connection URI/credentials into `.env`. A local `neo4j` Docker container
  also works (`NEO4J_URI=bolt://localhost:7687`).

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

- UI: http://localhost:5173 (proxies `/api` to the backend — make sure the
  backend above is running on port 8000; see `vite.config.js` for the proxy
  config).
- No environment variables are required for local dev. `VITE_API_KEY` is
  only needed if you've set `API_KEY` on the backend (see below).

## Environment variables

Defined in `backend/.env.example` — copy it to `backend/.env` and fill in
what you need:

| Variable | Required? | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | No | LLM-based graph extraction + GraphRAG queries via OpenRouter. Falls back to keyword matching if unset. |
| `OPENROUTER_MODEL` | No | Override the default model (`z-ai/glm-4.6`). |
| `OPENAI_API_KEY` | No | Alternative LLM provider (auto-selected over OpenRouter if only this is set). |
| `NEO4J_URI` / `NEO4J_USERNAME` / `NEO4J_PASSWORD` / `NEO4J_DATABASE` | No | Persist the graph to Neo4j and enable the Cypher Console. Persistence is skipped (not an error) if unset. |
| `ALLOWED_ORIGINS` | No | Extra comma-separated CORS origins beyond localhost + the deployed frontend. |
| `API_KEY` | No | Gates `/graph/build`, `/query`, and the `/requirements` write endpoints behind an `X-API-Key` header. Leave unset for an open local/demo setup. |
| `RATE_LIMIT_WINDOW_SECONDS` / `RATE_LIMIT_MAX_REQUESTS` | No | Per-IP rate limit on the two OpenRouter-backed endpoints. Defaults: 10 requests / 60s. |

If you set `API_KEY` on the backend, also set `VITE_API_KEY` in
`frontend/.env` to the same value, or the UI's requests will start getting
401s.

## Running tests

### Backend

```bash
cd backend
pytest -q
```

- The suite deliberately avoids hitting `/graph/build` or `/query` through
  the live TestClient (those call OpenRouter and would cost real API
  credits / make CI network-dependent). LLM-dependent logic is covered
  separately via mocked unit tests in `tests/test_llm_extractor.py`.
- CI runs this same `pytest -q` on every push/PR that touches `backend/**`
  (see `.github/workflows/test.yml`). A new backend feature should come with
  a test in the matching `tests/test_*.py` file — see `tests/test_api.py`
  for the house style (FastAPI `TestClient`, one assertion-focused test per
  behavior).

### Frontend

There is no frontend test suite yet (see the open issues if you'd like to
add one). At minimum, before opening a PR that touches `frontend/`:

```bash
cd frontend
npm run build
```

This catches syntax/type errors Vite would otherwise only surface at
runtime. Manually click through the affected panel(s) in `npm run dev` too.

## Code style

- **Backend**: standard FastAPI/Pydantic idioms already in the codebase —
  routers stay thin (validation + calling into `services/`), business logic
  lives in `services/`. Favor explicit, descriptive `HTTPException(status,
  detail=...)` over bare exceptions reaching the client. No linter is
  enforced in CI yet; just match the surrounding file's formatting.
- **Frontend**: functional components + hooks, Tailwind utility classes
  (see existing components for the established color/spacing conventions),
  `lib/api.js` as the single place that knows about backend endpoints — add
  new calls there rather than calling `axios`/`fetch` directly from a
  component.
- Keep PRs focused: one fix or feature per PR, not a drive-by reformat.

## PR process

1. Fork the repo (or create a branch if you have write access) and make
   your change on a feature branch, not `main`.
2. Make sure `pytest -q` (backend) and `npm run build` (frontend) pass for
   whichever side you touched.
3. Open a PR against `main` with:
   - A short description of **what** changed and **why**.
   - Which issue it addresses, if any (`Fixes #N`).
   - For UI changes, a before/after screenshot or short clip is appreciated
     but not required.
4. CI (`.github/workflows/test.yml`) runs automatically on backend changes.
   A PR that breaks it won't be merged until it's green.
5. Respond to review feedback on the PR itself — most feedback here is
   scoped to keeping the change minimal and consistent with the patterns
   above, not a deep architectural bar.

## Reporting bugs / proposing features

Open a GitHub issue using the existing title convention
(`[Bug] ...`, `[Feature] ...`, `[Docs] ...`, `[Security] ...`). Include:

- For bugs: what you did, what you expected, what happened, and which
  endpoint/component is involved.
- For features: the use case, not just the implementation — this helps
  scope the right-sized fix for a project this size.

Please don't open issues for API keys, Neo4j credentials, or anything
secret — those belong in your own `.env`, never in an issue or PR.
