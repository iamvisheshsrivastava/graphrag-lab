from fastapi import APIRouter, HTTPException
from models.schemas import QueryRequest, QueryResult
from services.rag_engine import rag_engine
import routers.graph as graph_router

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResult)
async def graphrag_query(request: QueryRequest):
    if graph_router._current_graph is None:
        raise HTTPException(400, detail="Build a knowledge graph first via POST /graph/build")
    return await rag_engine.query(request, graph_router._current_graph)
