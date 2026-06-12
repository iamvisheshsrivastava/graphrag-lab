"""
GraphRAG Engine — combines graph traversal context with LLM generation.

When OPENAI_API_KEY is set, uses GPT-4o for answer generation.
Without a key, falls back to a deterministic template-based response.
"""

import os
from typing import List, Optional

from models.schemas import QueryRequest, QueryResult, GraphNode, KnowledgeGraph
from services.graph_builder import graph_builder

try:
    from openai import AsyncOpenAI
    _openai_available = True
except ImportError:
    _openai_available = False


SYSTEM_PROMPT = """You are an expert in automotive requirements engineering for ADAS parking systems.
You have access to a domain-specific knowledge graph built from parking function requirements.
Answer questions with precision, referencing requirement IDs and ontology concepts.
Always cite the specific nodes and edges used in your reasoning (traceable answer).
Mention if requirements are incomplete, ambiguous, or conflict with ISO 26262 / SAE J3016 standards."""


class RAGEngine:
    def __init__(self):
        self._client: Optional[object] = None
        self._model = "gpt-4o"

    def _get_client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and _openai_available and self._client is None:
            self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    def _build_context(self, nodes: List[GraphNode], traversal_path: List[str]) -> str:
        """Serialize graph context into a prompt-friendly string."""
        lines = ["=== Retrieved Graph Context ==="]
        for node in nodes:
            lines.append(f"Node [{node.type}] {node.id}: {node.properties}")
        lines.append(f"\nTraversal path: {' → '.join(traversal_path[:10])}")
        return "\n".join(lines)

    def _fallback_answer(self, query: str, nodes: List[GraphNode], traversal_path: List[str]) -> str:
        """Deterministic answer template used when no LLM key is configured."""
        node_ids = [n.id for n in nodes]
        if not node_ids:
            return (
                f"No matching nodes found for query: '{query}'. "
                "Try adding more requirements or refining your search."
            )
        return (
            f"GraphRAG result for: '{query}'\n\n"
            f"Top relevant nodes: {', '.join(node_ids[:5])}\n"
            f"Graph traversal path: {' → '.join(traversal_path[:8])}\n\n"
            f"Based on the knowledge graph, the query touches {len(nodes)} concept(s). "
            f"Connect an OpenAI API key to enable full LLM-generated, traceable answers."
        )

    async def query(self, request: QueryRequest, graph: KnowledgeGraph) -> QueryResult:
        seed_nodes, traversal_path = graph_builder.graph_rag_retrieve(request.query, request.top_k)

        # Map seed_node IDs to GraphNode objects from the current graph
        node_map = {n.id: n for n in graph.nodes}
        relevant_nodes = [node_map[nid] for nid in seed_nodes if nid in node_map]

        context = self._build_context(relevant_nodes, traversal_path)
        confidence = min(1.0, len(relevant_nodes) / max(1, request.top_k))

        client = self._get_client()
        if client and request.use_llm:
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{context}\n\nQuestion: {request.query}"},
                ]
                response = await client.chat.completions.create(
                    model=self._model, messages=messages, temperature=0.1, max_tokens=800
                )
                answer = response.choices[0].message.content
            except Exception as e:
                answer = f"LLM call failed: {e}\n\n{self._fallback_answer(request.query, relevant_nodes, traversal_path)}"
        else:
            answer = self._fallback_answer(request.query, relevant_nodes, traversal_path)

        return QueryResult(
            query=request.query,
            answer=answer,
            relevant_nodes=relevant_nodes,
            traversal_path=traversal_path,
            confidence=confidence,
            sources=[n.id for n in relevant_nodes],
        )


rag_engine = RAGEngine()
