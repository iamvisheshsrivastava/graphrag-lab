from fastapi import APIRouter, HTTPException
from models.schemas import RequirementBatch, KnowledgeGraph, TraceabilityLink
from services.graph_builder import graph_builder

router = APIRouter(prefix="/graph", tags=["graph"])

# In-memory state — replace with Neo4j for production
_current_graph: KnowledgeGraph | None = None
_current_requirements = []


@router.post("/build", response_model=KnowledgeGraph)
def build_graph(batch: RequirementBatch):
    global _current_graph, _current_requirements
    _current_requirements = batch.requirements
    _current_graph = graph_builder.build_from_requirements(batch.requirements)
    return _current_graph


@router.get("/current", response_model=KnowledgeGraph)
def get_current_graph():
    if _current_graph is None:
        raise HTTPException(status_code=404, detail="No graph built yet. POST /graph/build first.")
    return _current_graph


@router.get("/traceability/{req_id}", response_model=list[TraceabilityLink])
def get_traceability(req_id: str):
    links = graph_builder.get_traceability(req_id)
    return links
