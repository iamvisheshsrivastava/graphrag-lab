# GraphRAG Parking Requirements Analyzer

> Domain-specific knowledge graph for automotive parking requirements, with verifiable Graph-Retrieval-Augmented-Generation (GraphRAG) queries.

Built as a practical demonstration of the research proposed in the **VW PhD position "AI-based GraphRAG Parking Functions"** (Wolfsburg, 2026).

---

## Research Context

This project addresses the core thesis of the PhD position:

> *Develop (nearly) deterministic, domain-specific knowledge graphs for structured representation of text-based requirements and their application in verifiable GraphRAG queries.*

| PhD Topic | This Project |
|---|---|
| Deterministic knowledge graph for requirements | `GraphBuilder` — ontology-guided, rule-based extraction |
| Domain-specific semantic model & ontology | `services/ontology.py` — parking/ADAS concept hierarchy |
| End-to-end scalable MVP | Full-stack: FastAPI backend + React frontend |
| Real-world SAE L2 parking requirements | 10-requirement sample dataset (`data/sample_requirements.json`) |
| Correctness, traceability, certifiability | Verification engine + traceability matrix UI |
| GraphRAG queries | LLM + graph traversal via `RAGEngine` |

---

## Architecture

```
graphrag-lab/
├── backend/
│   ├── main.py                   # FastAPI app entrypoint
│   ├── models/schemas.py         # Pydantic data models
│   ├── services/
│   │   ├── ontology.py           # ADAS parking ontology (concepts, relations, rules)
│   │   ├── graph_builder.py      # Deterministic KG construction + verification
│   │   └── rag_engine.py         # GraphRAG = graph traversal + LLM generation
│   ├── routers/
│   │   ├── requirements.py       # CRUD + batch verification
│   │   ├── graph.py              # Build & query knowledge graph
│   │   └── query.py              # GraphRAG query endpoint
│   └── data/
│       └── sample_requirements.json  # 10 SAE L2 parking requirements
│
└── frontend/
    ├── src/
    │   ├── App.jsx               # Root layout + state
    │   ├── components/
    │   │   ├── Sidebar.jsx       # Navigation
    │   │   ├── RequirementsPanel.jsx  # Load, view, manage requirements
    │   │   ├── GraphViewer.jsx   # Cytoscape.js interactive graph
    │   │   ├── QueryPanel.jsx    # GraphRAG query + answer display
    │   │   ├── VerificationPanel.jsx  # Rule-based ISO 26262 checks
    │   │   └── TraceabilityPanel.jsx  # Upstream/downstream trace links
    │   └── lib/api.js            # Axios API client
    └── package.json
```

---

## Features

### 1. Knowledge Graph Construction
- Extracts ontology concepts (sensors, functions, safety levels, actors) from requirement text
- Builds requirement-to-requirement dependency edges from cross-references (e.g. `REQ-003`)
- Detects semantic relations: `depends_on`, `refines`, `conflicts_with`, `derives_from`, `implements`
- Validates DAG property for certifiable topological ordering

### 2. Domain Ontology (`services/ontology.py`)
- Covers SAE J3016 L2 parking functions: APA, RPA, Summon
- Sensor hierarchy: Ultrasonic, Camera, Camera360, Radar, LiDAR
- ISO 26262 safety levels: ASIL-B, ASIL-D, QM
- Reasoning rules: safety propagation, sensor redundancy, L2 driver monitoring

### 3. GraphRAG Query Engine
- Graph traversal retrieves top-k relevant nodes by keyword matching
- BFS expansion to depth 2 for richer context
- Serialized context injected into GPT-4o prompt with domain system prompt
- Deterministic fallback when no API key is set

### 4. Requirements Verification
- Rule-based, deterministic checks (no LLM required):
  - SAE L2 must mention driver monitoring
  - Safety requirements must reference ISO 26262 / ASIL
  - Performance requirements must have quantitative thresholds
  - Ambiguity detection (`appropriate`, `adequate`, `as needed`, etc.)

### 5. Traceability Matrix
- Per-requirement upstream/downstream link explorer
- Suitable for certification evidence (ISO 26262 Part 8 — Traceability)

---

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Add your OpenAI key here
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

### Usage Flow

1. Go to **Requirements** tab → click **Load Sample Dataset**
2. Click **Build Knowledge Graph** → switches to the graph view
3. Explore the **Knowledge Graph** — click nodes for details
4. Go to **GraphRAG Query** → ask natural language questions
5. Go to **Verification** → run ISO 26262 checks
6. Go to **Traceability** → explore dependency chains

---

## Adding Your OpenAI Key

Create `backend/.env`:

```
OPENAI_API_KEY=sk-...
```

The backend auto-detects the key. The `/` endpoint shows `"llm_enabled": true` when active.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| NetworkX (not Neo4j) for MVP | Zero infrastructure, pure Python, easy to swap |
| Deterministic ontology extraction | Reproducible & verifiable — no probabilistic NER |
| Rule-based verification | Certifiable evidence; no black-box ML |
| Cytoscape.js for graph viz | Lightweight, no server-side rendering, supports 1000s of nodes |
| React + Vite | Fast dev server, minimal config, modern ecosystem |

---

## Roadmap

- [ ] Neo4j / AuraDB integration for persistent graph storage
- [ ] spaCy-based named entity extraction for richer ontology linking
- [ ] Cypher query generation for `MATCH (r:Requirement)-[:DEPENDS_ON]->(r2)` style traversal
- [ ] SHACL / SPARQL constraint validation
- [ ] Export to ReqIF format for DOORS / Polarion integration
- [ ] Multi-document requirement parsing (PDF, DOCX)
- [ ] Conflict detection via constraint propagation
- [ ] Docker Compose for one-command startup

---

## References

- SAE J3016: Taxonomy for Driving Automation (2021)
- ISO 26262: Road vehicles — Functional safety
- Edge, D. et al. (2024). *From Local to Global: A Graph RAG Approach to Query-Focused Summarization.* arXiv:2404.16130
- Baader, F. et al. (2003). *The Description Logic Handbook.* Cambridge University Press.
