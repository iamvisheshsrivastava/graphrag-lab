"""
GraphRAG Parking Requirements Analyzer — FastAPI Backend

Run with:
    uvicorn main:app --reload --port 8000

Docs available at: http://localhost:8000/docs
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import graph, requirements, query
from services.neo4j_service import ensure_constraints

load_dotenv()

app = FastAPI(
    title="GraphRAG — Automotive Requirements Knowledge Graph",
    description=(
        "Deterministic knowledge graph construction and GraphRAG querying over "
        "automotive ADAS requirements. Supports SAE L2 parking functions with "
        "ISO 26262 verification and full traceability."
    ),
    version="0.1.0",
)

import os as _os

# Known, exact production frontend origin (see README "Frontend (Vercel)").
# No wildcard regex — that would whitelist every *.vercel.app deployment on
# the internet, not just this project's (see issue #3).
_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://graphrag-lab.vercel.app",
]
_extra = _os.getenv("ALLOWED_ORIGINS", "")
if _extra:
    _allowed_origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# issue #2: optional shared-API-key auth + per-IP rate limiting on the
# cost-sensitive endpoints. See backend/security.py for the implementation.
# API_KEY unset -> fully open (today's public-demo behavior, unchanged).
# API_KEY set -> POST /graph/build, POST /query, and the /requirements
# write endpoints require a matching X-API-Key header; /graph/build and
# POST /query (the two OpenRouter-calling endpoints) are additionally
# rate-limited per IP. Cheap read endpoints (/health, /graph/current, etc.)
# stay ungated.
app.include_router(requirements.router)
app.include_router(graph.router)
app.include_router(query.router)


@app.on_event("startup")
def _startup():
    # Idempotent — creates per-label id-uniqueness constraints in Neo4j if
    # not already present. No-op if Neo4j isn't configured. See issue #10.
    ensure_constraints()
    # Repopulate in-memory graph from Neo4j after a restart, if available.
    # No-op if Neo4j isn't configured or nothing has been persisted yet.
    # See issue #6.
    graph.reload_from_neo4j()


@app.get("/")
def root():
    return {
        "project": "GraphRAG — Automotive Requirements Knowledge Graph",
        "version": "0.1.0",
        "docs": "/docs",
        "llm_enabled": bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")),
        "llm_provider": "openrouter" if os.getenv("OPENROUTER_API_KEY") else ("openai" if os.getenv("OPENAI_API_KEY") else "none"),
    }


@app.get("/health")
def health():
    # Used by frontend wake-on-mount to pre-warm Render free tier instance (redeploy trigger)
    return {"status": "ok"}
