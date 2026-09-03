from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.schemas import RequirementBatch, KnowledgeGraph, TraceabilityLink
from services.graph_builder import graph_builder
from services.neo4j_service import persist_graph, neo4j_status, load_graph
from security import require_api_key, rate_limit_llm
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

# In-memory state (NetworkX) — fast traversal for GraphRAG retrieval
# Neo4j AuraDB stores the same graph for durable Cypher queries across restarts
#
# KNOWN LIMITATION (issue #6, partially addressed):
# This state is still a module-level global, which means: (1) it is NOT safe
# if uvicorn is ever run with --workers > 1 (each worker gets its own copy,
# so requests would see inconsistent state), and (2) every caller shares one
# global graph — one user's POST /graph/build silently replaces another's.
# query.py also reaches into this module's private global
# (graph_router._current_graph), which is a brittle cross-module coupling.
# What *is* now fixed: on startup (see main.py's `_startup`), if Neo4j is
# configured and has previously-persisted data, `reload_from_neo4j()`
# below repopulates `_current_graph` so a Render free-tier restart no longer
# forces every user back to "no graph built yet" — the original TODO here.
# The remaining work (GraphStore service + dependency injection, eventually
# per-session/per-graph IDs) is a real architectural change and is
# deliberately not attempted in this pass — see issue #6.
_current_graph: KnowledgeGraph | None = None
_current_requirements = []


def reload_from_neo4j() -> bool:
    """Called once at startup. If no graph is in memory yet and Neo4j has a
    previously-persisted graph, load it so a service restart doesn't force
    a rebuild. No-op (returns False) if a graph is already in memory, Neo4j
    isn't configured, or there's nothing persisted yet."""
    global _current_graph
    if _current_graph is not None:
        return False
    data = load_graph()
    if data is None:
        return False
    try:
        _current_graph = KnowledgeGraph(**data)
        logger.info(
            "Reloaded graph from Neo4j on startup (%d nodes, %d edges)",
            len(data["nodes"]), len(data["edges"]),
        )
        return True
    except Exception as e:
        logger.error("Failed to parse graph reloaded from Neo4j: %s", e)
        return False


@router.post(
    "/build",
    response_model=KnowledgeGraph,
    dependencies=[Depends(require_api_key), Depends(rate_limit_llm)],
)
def build_graph(batch: RequirementBatch):
    global _current_graph, _current_requirements
    _current_requirements = batch.requirements
    _current_graph = graph_builder.build_from_requirements(batch.requirements)

    # Persist to Neo4j AuraDB (non-blocking — failure doesn't break the response)
    try:
        graph_dict = _current_graph.model_dump()
        ok = persist_graph(graph_dict)
        if ok:
            logger.info("Graph persisted to Neo4j")
        else:
            logger.warning("Neo4j persistence skipped (not configured or unavailable)")
    except Exception as e:
        logger.error("Neo4j persist error (non-fatal): %s", e)

    return _current_graph


@router.get("/neo4j/status")
def get_neo4j_status():
    return neo4j_status()


@router.get("/current", response_model=KnowledgeGraph)
def get_current_graph():
    if _current_graph is None:
        raise HTTPException(status_code=404, detail="No graph built yet. POST /graph/build first.")
    return _current_graph


@router.get("/stats")
def get_graph_stats():
    """Quick graph health summary — useful for debugging and front-end dashboards."""
    if _current_graph is None:
        return {"built": False}
    node_types: dict = {}
    for n in _current_graph.nodes:
        t = n.type
        node_types[t] = node_types.get(t, 0) + 1
    rel_types: dict = {}
    for e in _current_graph.edges:
        r = e.relation
        rel_types[r] = rel_types.get(r, 0) + 1
    return {
        "built": True,
        "extraction": _current_graph.metadata.get("extraction", "unknown"),
        "node_count": len(_current_graph.nodes),
        "edge_count": len(_current_graph.edges),
        "node_types": node_types,
        "relation_types": rel_types,
        "is_dag": _current_graph.metadata.get("is_dag", None),
    }


@router.get("/traceability/{req_id}", response_model=list[TraceabilityLink])
def get_traceability(req_id: str):
    links = graph_builder.get_traceability(req_id)
    return links
