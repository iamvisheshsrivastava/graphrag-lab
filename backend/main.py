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

# KNOWN LIMITATION (issue #2, deliberately out of scope for this pass):
# No authentication or rate limiting on any endpoint. Two concrete abuse
# paths: (1) POST /query/ and /graph/build call the paid OpenRouter API, so
# an unauthenticated bot hammering this public URL directly drains the
# OPENROUTER_API_KEY budget; (2) POST /requirements/ and /requirements/batch
# let anyone write into the shared in-memory store, polluting state for all
# users. Payload sizes are now bounded (issue #11), which limits per-request
# blast radius, but does not stop repeated/automated abuse. A real fix needs
# a design decision (API-key header via FastAPI Depends on mutating/LLM
# endpoints, e.g. slowapi-based per-IP rate limiting) that's out of scope
# for this pass — flagging here rather than guessing at auth requirements.
app.include_router(requirements.router)
app.include_router(graph.router)
app.include_router(query.router)


@app.on_event("startup")
def _startup():
    # Idempotent — creates per-label id-uniqueness constraints in Neo4j if
    # not already present. No-op if Neo4j isn't configured. See issue #10.
    ensure_constraints()


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
