# GraphRAG — Automotive Requirements Knowledge Graph

A research tool for building **deterministic, domain-specific knowledge graphs** from automotive requirements text and querying them using **Graph-Retrieval-Augmented-Generation (GraphRAG)**.

The system targets ADAS and parking function requirements (SAE Level 2), supporting formal traceability, consistency verification, and natural language querying grounded in an automotive ontology.

---

## Motivation

Requirements engineering in safety-critical systems (ISO 26262, SOTIF) involves large, interdependent sets of textual requirements. Analysing their dependencies, detecting ambiguities, and producing certification evidence is largely manual today.

This project explores how knowledge graphs combined with LLM-based retrieval can make requirements analysis:
- **Deterministic** — same inputs always produce the same graph structure
- **Traceable** — every answer cites the graph nodes and edges it used
- **Verifiable** — rule-based checks enforce domain standards without black-box ML
- **Queryable** — natural language queries traversed via the graph before LLM generation

---

## Architecture

```
graphrag-lab/
├── backend/
│   ├── main.py                       # FastAPI app entrypoint
│   ├── models/schemas.py             # Pydantic data models
│   ├── services/
│   │   ├── ontology.py               # Automotive parking ontology (concepts, relations, rules)
│   │   ├── graph_builder.py          # Deterministic KG construction + verification engine
│   │   └── rag_engine.py             # GraphRAG = graph traversal + LLM generation
│   ├── routers/
│   │   ├── requirements.py           # CRUD + batch verification endpoints
│   │   ├── graph.py                  # Build & inspect knowledge graph
│   │   └── query.py                  # GraphRAG query endpoint
│   └── data/
│       └── sample_requirements.json  # 30 SAE L2 ADAS parking requirements
│
└── frontend/
    ├── src/
    │   ├── App.jsx                   # Root layout + state
    │   ├── components/
    │   │   ├── Sidebar.jsx           # Navigation
    │   │   ├── RequirementsPanel.jsx # Load, view, and manage requirements
    │   │   ├── GraphViewer.jsx       # Cytoscape.js interactive graph canvas
    │   │   ├── QueryPanel.jsx        # GraphRAG query + answer display
    │   │   ├── VerificationPanel.jsx # Rule-based ISO 26262 / SAE checks
    │   │   └── TraceabilityPanel.jsx # Upstream/downstream dependency explorer
    │   └── lib/api.js                # Axios API client
    └── package.json
```

---

## Features

### 1. Knowledge Graph Construction
- Ontology-guided, keyword-based entity extraction — no probabilistic NER
- Builds requirement-to-requirement dependency edges from explicit cross-references (e.g. `REQ-003`)
- Detects semantic relations: `depends_on`, `refines`, `conflicts_with`, `derives_from`, `implements`, `mentions`
- Validates DAG property; topological ordering enables certifiable dependency analysis

### 2. Domain Ontology
Defined in `services/ontology.py`, covering:
- **Functions:** AutomaticParkingAssist (APA), RemoteParkingAssist (RPA), SummonFunction
- **Sensors:** UltrasonicSensor, Camera, Camera360, Radar, LiDAR
- **Safety levels:** ASIL-B, ASIL-D, QM (ISO 26262)
- **Actors:** Driver, Pedestrian, Vehicle
- **Reasoning rules:** safety propagation, sensor redundancy, SAE L2 driver monitoring obligation

### 3. GraphRAG Query Engine
- Top-k node retrieval by keyword scoring against the graph
- BFS context expansion to depth 2 around seed nodes
- Graph context serialized and injected into LLM prompt alongside the query
- Fully deterministic fallback when no LLM key is configured

### 4. Requirements Verification
Rule-based, reproducible checks — no LLM required:
- SAE L2 requirements must include a driver monitoring obligation
- Safety requirements must reference an ISO 26262 ASIL level
- Performance requirements must contain quantitative thresholds
- Ambiguous language detection (`appropriate`, `adequate`, `as needed`, `if possible`, …)

### 5. Traceability Matrix
- Per-requirement upstream and downstream link explorer
- Link types: `depends_on`, `derives_from`, `implements`, `conflicts_with`
- Output format suitable for ISO 26262 Part 8 traceability evidence

---

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # optional: add LLM key for AI-powered answers
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at: http://localhost:5173

### Walkthrough

1. **Requirements** tab → click **Load Sample Dataset** (30 ADAS parking requirements)
2. Click **Build Knowledge Graph** → the app switches to the graph view automatically
3. **Knowledge Graph** → click any node to inspect its properties and ontology links
4. **GraphRAG Query** → ask natural language questions; see the graph traversal path used
5. **Verification** → run deterministic ISO 26262 / SAE J3016 consistency checks
6. **Traceability** → select any requirement to explore its full dependency chain

---

## LLM Configuration

The system works offline without an LLM key (deterministic graph-based answers). To enable AI-generated, grounded responses, create `backend/.env`:

```env
# OpenRouter (free models available)
OPENROUTER_API_KEY=sk-or-...

# Or standard OpenAI
OPENAI_API_KEY=sk-...
```

The backend auto-detects the key on startup. The root endpoint (`GET /`) reports `"llm_enabled": true` when active.

Tested with `google/gemma-4-31b-it:free` via OpenRouter.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| Deterministic ontology extraction over NER | Reproducible graph structure; no stochastic variance between runs |
| Rule-based verification (no ML) | Certifiable, auditable evidence for functional safety standards |
| NetworkX in-memory graph for MVP | Zero infrastructure dependency; Neo4j/AuraDB drop-in for production |
| Cytoscape.js for visualization | Handles large graphs client-side; no server render needed |
| React + Vite | Lightweight dev stack; fast HMR; minimal configuration |

---

## Roadmap

- [ ] Neo4j / AuraDB integration for persistent graph storage and Cypher queries
- [ ] spaCy or custom NER for richer, automated ontology concept extraction
- [ ] SHACL / SPARQL constraint validation layer
- [ ] Export to ReqIF format for integration with DOORS / Polarion
- [ ] Multi-document ingestion (PDF, DOCX, Excel requirement sheets)
- [ ] Conflict detection via constraint propagation and SAT solving
- [ ] Docker Compose for one-command local deployment

---

## References

- SAE J3016: *Taxonomy and Definitions for Terms Related to Driving Automation Systems* (2021)
- ISO 26262: *Road vehicles — Functional safety* (2018)
- ISO 21448: *Road vehicles — Safety of the intended functionality (SOTIF)* (2022)
- Edge, D. et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv:2404.16130
- Baader, F. et al. (2003). *The Description Logic Handbook.* Cambridge University Press.
- Pan, J.Z. et al. (2023). *Unifying Large Language Models and Knowledge Graphs: A Roadmap.* IEEE TKDE.
