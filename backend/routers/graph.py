from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.schemas import RequirementBatch, KnowledgeGraph, TraceabilityLink
from services.graph_builder import graph_builder
from services.neo4j_service import persist_graph, neo4j_status, load_graph
from services.state import store
from security import require_api_key, rate_limit_llm
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["graph"])

# State lives in services.state.GraphStore (issue #6). Still per-process:
# not shared across uvicorn workers and one global graph for all callers.
# On startup, reload_from_neo4j() repopulates it from Neo4j.


def reload_from_neo4j() -> bool:
    """Called once at startup. If no graph is in memory yet and Neo4j has a
    previously-persisted graph, load it so a service restart doesn't force
    a rebuild. No-op (returns False) if a graph is already in memory, Neo4j
    isn't configured, or there's nothing persisted yet."""
    if store.graph is not None:
        return False
    data = load_graph()
    if data is None:
        return False
    try:
        store.graph = KnowledgeGraph(**data)
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
    graph = graph_builder.build_from_requirements(batch.requirements)
    store.set_graph(graph, batch.requirements)

    # Persist to Neo4j AuraDB (non-blocking — failure doesn't break the response)
    try:
        graph_dict = graph.model_dump()
        ok = persist_graph(graph_dict)
        if ok:
            logger.info("Graph persisted to Neo4j")
        else:
            logger.warning("Neo4j persistence skipped (not configured or unavailable)")
    except Exception as e:
        logger.error("Neo4j persist error (non-fatal): %s", e)

    return graph


@router.get("/neo4j/status")
def get_neo4j_status():
    return neo4j_status()


@router.get("/current", response_model=KnowledgeGraph)
def get_current_graph():
    graph = store.graph
    if graph is None:
        raise HTTPException(status_code=404, detail="No graph built yet. POST /graph/build first.")
    return graph


@router.get("/stats")
def get_graph_stats():
    """Quick graph health summary — useful for debugging and front-end dashboards."""
    if store.graph is None:
        return {"built": False}
    node_types: dict = {}
    for n in store.graph.nodes:
        t = n.type
        node_types[t] = node_types.get(t, 0) + 1
    rel_types: dict = {}
    for e in store.graph.edges:
        r = e.relation
        rel_types[r] = rel_types.get(r, 0) + 1
    return {
        "built": True,
        "extraction": store.graph.metadata.get("extraction", "unknown"),
        "node_count": len(store.graph.nodes),
        "edge_count": len(store.graph.edges),
        "node_types": node_types,
        "relation_types": rel_types,
        "is_dag": store.graph.metadata.get("is_dag", None),
    }


@router.get("/traceability/{req_id}", response_model=list[TraceabilityLink])
def get_traceability(req_id: str):
    links = graph_builder.get_traceability(req_id)
    return links
