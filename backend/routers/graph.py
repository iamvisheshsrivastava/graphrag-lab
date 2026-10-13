from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from models.schemas import RequirementBatch, KnowledgeGraph, TraceabilityLink
from services.graph_builder import graph_builder
from services.neo4j_service import persist_graph, neo4j_status, load_graph
from services.state import store
from services import graph_export, graph_diff
from security import require_api_key, rate_limit_llm
import json
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
        # Also rebuild the NetworkX graph that graph_builder.detect_conflicts()
        # and graph_builder.get_traceability() read from. store.graph alone
        # isn't enough — those methods never look at it (see issue #20).
        graph_builder.load_from_knowledge_graph(store.graph)
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


# ─── Export (issue #14) ───────────────────────────────────────────────────────

_EXPORT_CONTENT = {
    "graphml": ("application/xml", "graph.graphml"),
    "cypher": ("text/plain", "graph.cypher"),
    "jsonld": ("application/ld+json", "graph.jsonld"),
}


@router.get("/export")
def export_graph(format: str = "graphml"):
    """Serialize the current in-memory graph (store.graph — the single
    shared in-process graph, see issue #6) to a portable interchange format:
    GraphML (Gephi/yEd), a Cypher MERGE script, or JSON-LD."""
    if format not in _EXPORT_CONTENT:
        raise HTTPException(400, detail="format must be one of: graphml, cypher, jsonld")

    graph = store.graph
    if graph is None:
        raise HTTPException(400, detail="Build a knowledge graph first via POST /graph/build")

    if format == "graphml":
        content = graph_export.to_graphml(graph)
    elif format == "cypher":
        content = graph_export.to_cypher(graph)
    else:
        content = json.dumps(graph_export.to_jsonld(graph), indent=2)

    media_type, filename = _EXPORT_CONTENT[format]
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Named snapshots + diff (issue #16) ───────────────────────────────────────
# In-memory only (services.state.GraphStore.snapshots) — same singleton/
# per-process caveats as the rest of the shared graph state (issue #6).


class SnapshotCreateRequest(BaseModel):
    name: str


@router.post("/snapshots", dependencies=[Depends(require_api_key)])
def create_snapshot(req: SnapshotCreateRequest):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, detail="Snapshot name must not be empty")
    try:
        snap = store.save_snapshot(name)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {
        "name": name,
        "created_at": snap["created_at"],
        "node_count": len(snap["graph"].nodes),
        "edge_count": len(snap["graph"].edges),
    }


@router.get("/snapshots")
def list_snapshots():
    return store.list_snapshots()


@router.get("/snapshots/diff")
def diff_snapshots(a: str, b: str):
    graph_a = store.get_snapshot(a)
    graph_b = store.get_snapshot(b)
    if graph_a is None:
        raise HTTPException(404, detail=f"Snapshot '{a}' not found")
    if graph_b is None:
        raise HTTPException(404, detail=f"Snapshot '{b}' not found")
    return graph_diff.diff_graphs(graph_a, graph_b)
