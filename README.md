# GraphRAG — Automotive Requirements Knowledge Graph

A research tool for building **LLM-powered, domain-specific knowledge graphs** from automotive requirements text and querying them using **Graph-Retrieval-Augmented-Generation (GraphRAG)**.

Targets ADAS and parking function requirements (SAE Level 2) with full traceability, consistency verification, natural language querying, and persistent graph storage via Neo4j AuraDB.

Built as a portfolio project supporting a PhD application in AI-based GraphRAG for automotive functions.

---

## Live Demo

| Layer | URL |
|---|---|
| Frontend (Vercel) | https://graphrag-lab.vercel.app |
| Backend API (Render) | https://graphrag-lab-api.onrender.com |
| API Docs (Swagger) | https://graphrag-lab-api.onrender.com/docs |

> **Note:** The backend runs on Render's free tier and may take ~50 seconds to wake from cold start.

---

## Architecture

```
graphrag-lab/
├── backend/
│   ├── main.py                       # FastAPI app entrypoint + CORS config
│   ├── .python-version               # Pins Python 3.11.0 for Render
│   ├── models/schemas.py             # Pydantic data models
│   ├── services/
│   │   ├── ontology.py               # Automotive parking ontology (concepts, relations, rules)
│   │   ├── llm_extractor.py          # LLM-based entity + relation extraction (gemini-2.5-flash)
│   │   ├── graph_builder.py          # KG construction: LLM extraction → ontology backbone
│   │   ├── neo4j_service.py          # Neo4j AuraDB persistence + Cypher query runner
│   │   └── rag_engine.py             # GraphRAG = BFS traversal + LLM generation
│   ├── routers/
│   │   ├── requirements.py           # CRUD + batch verification endpoints
│   │   ├── graph.py                  # Build, inspect, Neo4j status endpoints
│   │   └── query.py                  # GraphRAG query + Cypher passthrough endpoints
│   └── data/
│       └── sample_requirements.json  # 18 rich ADAS parking requirements (SYS/APA/RPA/SUM/SEN/HMI/VER)
│
└── frontend/
    ├── src/
    │   ├── App.jsx                   # Root layout + routing
    │   ├── components/
    │   │   ├── Sidebar.jsx           # Navigation (6 tabs)
    │   │   ├── RequirementsPanel.jsx # Load sample data or upload JSON/CSV
    │   │   ├── GraphViewer.jsx       # Cytoscape.js interactive graph canvas
    │   │   ├── QueryPanel.jsx        # GraphRAG natural language query + answer
    │   │   ├── VerificationPanel.jsx # Rule-based ISO 26262 / SAE J3016 checks
    │   │   ├── TraceabilityPanel.jsx # Upstream/downstream dependency explorer
    │   │   └── CypherConsole.jsx     # Live Cypher query editor against Neo4j AuraDB
    │   └── lib/api.js                # Axios API client + all endpoint wrappers
    └── package.json
```

---

## Features

### 1. LLM-Based Knowledge Graph Construction

Graph building is a two-step pipeline:

**Step 1 — LLM extraction** (`llm_extractor.py`)
- Sends the full requirements batch to `google/gemini-2.5-flash` via OpenRouter in a single structured prompt
- Returns strict JSON: `{"entities": [...], "relations": [...]}`
- Temperature = 0.0 for near-deterministic output
- Entity types: `sensor | function | concept | actor | safety_level | standard | system`
- Relation types: `mentions | depends_on | derives_from | implements | governed_by | conflicts_with | refines | part_of | uses | connected_to`
- Falls back to keyword matching if no API key is set

**Step 2 — Ontology backbone** (`graph_builder.py`)
- Merges LLM output with deterministic ontology edges defined in `ontology.py`
- Scans requirement text for explicit cross-references (e.g. `APA-001`) and adds `depends_on` edges
- Validates DAG property; topological ordering enables certifiable dependency analysis

### 2. Neo4j AuraDB Integration

- After every graph build, the full graph is persisted to Neo4j AuraDB via Cypher `MERGE`
- Node labels: `:Requirement` and `:Entity`
- In-memory NetworkX DiGraph is used for fast BFS traversal during GraphRAG retrieval
- Neo4j failure is non-blocking — API response is not affected if Neo4j is down

### 3. Cypher Console

- Live query editor in the UI with 6 example Cypher queries pre-loaded
- Shows Neo4j connection status + node count badge
- Results rendered as a sortable table (columns + rows)
- Ctrl+Enter to run — calls `POST /query/cypher` on the backend

### 4. GraphRAG Query Engine

- Top-k node retrieval by TF-IDF-style keyword scoring against the graph
- BFS context expansion (depth 2) around seed nodes
- Graph context serialized into the LLM prompt alongside the question
- Answer is grounded in cited graph nodes — every response includes the traversal path
- Model: `google/gemini-2.5-flash` via OpenRouter

### 5. Requirements Input

- **Load sample dataset** — 18 rich automotive requirements covering SYS, APA, RPA, SUM, SEN, HMI, VER domains
- **Upload your own** — supports `.json` (array of requirement objects) and `.csv` files

### 6. Verification Engine

Rule-based, deterministic checks (no LLM required):
- SAE L2 requirements must include a driver monitoring obligation
- Safety requirements must reference an ISO 26262 ASIL level
- Performance requirements must contain quantitative thresholds
- Ambiguous language detection (`appropriate`, `adequate`, `as needed`, `if possible`, …)

### 7. Traceability Matrix

- Per-requirement upstream and downstream link explorer
- Link types: `depends_on`, `derives_from`, `implements`, `conflicts_with`
- Output suitable for ISO 26262 Part 8 traceability evidence

---

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # add your keys
uvicorn main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://localhost:5173

### Walkthrough

1. **Requirements** → **Load Sample Dataset** (18 ADAS parking requirements)
2. **Knowledge Graph** → **Generate Graph** (LLM extracts entities + relations)
3. Click any node to inspect its properties and ontology links
4. **GraphRAG Query** → ask natural language questions; see the traversal path used
5. **Verification** → run ISO 26262 / SAE J3016 consistency checks
6. **Traceability** → explore upstream/downstream dependency chains
7. **Cypher Console** → run live Cypher queries against Neo4j AuraDB

---

## Environment Variables

Create `backend/.env`:

```env
# Required for LLM-based graph extraction and GraphRAG queries
OPENROUTER_API_KEY=sk-or-v1-...

# Optional: override the model (default: google/gemini-2.5-flash)
OPENROUTER_MODEL=google/gemini-2.5-flash

# Required for Neo4j AuraDB persistence and Cypher Console
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Or use OpenAI directly (model switches to gpt-4o automatically)
OPENAI_API_KEY=sk-...
```

The root endpoint (`GET /`) reports `"llm_enabled": true / false` and `"llm_provider": "openrouter" | "openai" | "none"`.

Without any API key, the system falls back to keyword-based graph extraction and template-based query answers — fully functional for offline/demo use.

---

## Model Choice

| Model | Provider | Cost | Used for |
|---|---|---|---|
| `google/gemini-2.5-flash` | OpenRouter | ~$0.15/1M tokens | Graph extraction + GraphRAG queries |
| `gpt-4o` | OpenAI | ~$2.50/1M tokens | Auto-selected if only `OPENAI_API_KEY` is set |

At typical demo usage (10 graph builds + 50 queries), total cost ≈ **$0.01–0.02**.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| LLM extraction at temperature=0.0 | Near-deterministic graph structure; consistent across runs |
| Ontology backbone merged after LLM | Guarantees domain concepts are always present regardless of LLM output |
| Dual storage: NetworkX + Neo4j | NetworkX for fast in-process BFS; Neo4j for durable Cypher queries |
| Rule-based verification (no ML) | Certifiable, auditable evidence for ISO 26262 functional safety |
| Cytoscape.js for visualization | Handles large graphs client-side; no server render needed |
| OpenRouter as LLM gateway | Single API key accesses 100+ models; easy model switching via env var |
| Render free tier + Vercel CDN | Zero-cost hosting for portfolio demo |

---

## Roadmap

- [x] LLM-based entity + relation extraction
- [x] Neo4j AuraDB integration for persistent Cypher-queryable graph storage
- [x] Cypher Console in UI
- [x] File upload for custom requirements (JSON / CSV)
- [ ] Reload graph from Neo4j on service restart (currently requires manual rebuild)
- [ ] SHACL / SPARQL constraint validation layer
- [ ] Export to ReqIF format for integration with DOORS / Polarion
- [ ] Multi-document ingestion (PDF, DOCX, Excel requirement sheets)
- [ ] Conflict detection via constraint propagation and SAT solving
- [ ] Docker Compose for one-command local deployment

---

## References

- SAE J3016: *Taxonomy and Definitions for Terms Related to Driving Automation Systems* (2021)
- ISO 26262: *Road vehicles — Functional safety* (2018)
- ISO 21448: *Road vehicles — Safety of the Intended Functionality (SOTIF)* (2022)
- Edge, D. et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv:2404.16130
- Baader, F. et al. (2003). *The Description Logic Handbook.* Cambridge University Press.
- Pan, J.Z. et al. (2023). *Unifying Large Language Models and Knowledge Graphs: A Roadmap.* IEEE TKDE.
