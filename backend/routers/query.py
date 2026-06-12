from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.schemas import QueryRequest, QueryResult
from services.rag_engine import rag_engine
from services.neo4j_service import run_cypher
import routers.graph as graph_router

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/", response_model=QueryResult)
async def graphrag_query(request: QueryRequest):
    if graph_router._current_graph is None:
        raise HTTPException(400, detail="Build a knowledge graph first via POST /graph/build")
    return await rag_engine.query(request, graph_router._current_graph)


class CypherRequest(BaseModel):
    query: str
    params: dict = {}


@router.post("/cypher")
def cypher_query(req: CypherRequest):
    """
    Execute a Cypher query against Neo4j AuraDB.
    Only read queries (MATCH/RETURN) are recommended.
    """
    if not req.query.strip():
        raise HTTPException(400, detail="Query must not be empty")
    result = run_cypher(req.query, req.params)
    if "error" in result:
        raise HTTPException(500, detail=result["error"])
    return result
