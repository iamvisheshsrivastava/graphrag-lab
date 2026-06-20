from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.schemas import RequirementBatch, KnowledgeGraph, TraceabilityLink
from services.graph_builder import graph_builder
from services.neo4j_service import persist_graph, neo4j_status
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

# In-memory state (NetworkX) — fast traversal for GraphRAG retrieval
# Neo4j AuraDB stores the same graph for durable Cypher queries across restarts
# TODO: on service restart, reload graph from Neo4j instead of requiring a rebuild
_current_graph: KnowledgeGraph | None = None
_current_requirements = []


@router.post("/build", response_model=KnowledgeGraph)
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
