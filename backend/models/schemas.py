from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    SAFETY = "safety"
    INTERFACE = "interface"
    PERFORMANCE = "performance"


class SAELevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class Requirement(BaseModel):
    id: str
    text: str
    type: RequirementType = RequirementType.FUNCTIONAL
    sae_level: SAELevel = SAELevel.L2
    domain: str = "parking"
    tags: List[str] = []
    source: Optional[str] = None


class RequirementBatch(BaseModel):
    requirements: List[Requirement]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # requirement, entity, concept, sensor, function
    properties: dict = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str  # depends_on, implements, uses, conflicts_with, refines, derives_from
    weight: float = 1.0


class KnowledgeGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: dict = {}


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    use_llm: bool = True


class QueryResult(BaseModel):
    query: str
    answer: str
    relevant_nodes: List[GraphNode]
    traversal_path: List[str]
    confidence: float
    sources: List[str]


class TraceabilityLink(BaseModel):
    source_id: str
    target_id: str
    link_type: str
    rationale: str


class VerificationResult(BaseModel):
    requirement_id: str
    status: str  # verified, conflict, incomplete, ambiguous
    issues: List[str]
    suggestions: List[str]
