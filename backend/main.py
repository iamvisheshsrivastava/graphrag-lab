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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(requirements.router)
app.include_router(graph.router)
app.include_router(query.router)


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
    return {"status": "ok"}
