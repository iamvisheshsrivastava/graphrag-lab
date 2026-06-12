"""
Knowledge Graph Builder for automotive parking requirements.

Build strategy:
  1. Call LLM (gemini-2.0-flash via OpenRouter) to extract entities + relations
     from the full requirements batch in one structured JSON call.
  2. Merge LLM output with deterministic ontology backbone edges.
  3. Persist the NetworkX graph for in-process GraphRAG retrieval.
  4. Caller (router) writes to Neo4j separately via neo4j_service.

Falls back to keyword-based extraction if LLM is unavailable.
"""

import re
import networkx as nx
from typing import List, Tuple

from models.schemas import (
    Requirement, KnowledgeGraph, GraphNode, GraphEdge,
    TraceabilityLink, VerificationResult,
)
from services.ontology import PARKING_ONTOLOGY
from services.llm_extractor import extract_graph_from_requirements


# ─── Fallback keyword maps (used when LLM is unavailable) ────────────────────

ENTITY_KEYWORDS = {
    "UltrasonicSensor":       ["ultrasonic", "USS", "proximity sensor"],
    "Camera":                 ["camera", "vision", "image"],
    "Camera360":              ["surround view", "360", "bird-eye"],
    "Radar":                  ["radar", "FMCW"],
    "LiDAR":                  ["lidar", "laser"],
    "Driver":                 ["driver", "operator", "user"],
    "Pedestrian":             ["pedestrian", "person", "cyclist"],
    "ParkingSpace":           ["parking space", "slot", "bay"],
    "RemoteParkingAssist":    ["remote parking", "RPA"],
    "AutomaticParkingAssist": ["APA", "automatic park", "auto park"],
    "SummonFunction":         ["summon", "home-to-me"],
    "ASIL_B":                 ["ASIL-B", "ASIL B"],
    "ASIL_D":                 ["ASIL-D", "ASIL D"],
    "ISO26262":               ["ISO 26262", "ISO26262", "functional safety"],
    "SOTIF":                  ["SOTIF", "ISO 21448"],
    "VehicleECU":             ["ECU", "electronic control unit", "controller"],
    "TrajectoryPlanner":      ["trajectory", "path planning", "motion planner"],
    "ObstacleDetection":      ["obstacle", "object detection", "collision"],
}

DEPENDENCY_KEYWORDS = {
    "depends_on":     ["depends on", "requires", "needs", "shall use", "must use"],
    "refines":        ["refines", "specializes", "is a type of"],
    "conflicts_with": ["conflicts with", "contradicts", "mutually exclusive"],
    "derives_from":   ["derived from", "allocated to", "traces to"],
    "implements":     ["implements", "realizes", "satisfies"],
}


class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    # ─── LLM-based build ──────────────────────────────────────────────────────

    def build_from_requirements(self, requirements: List[Requirement]) -> KnowledgeGraph:
        """
        Build a knowledge graph from requirements.
        Tries LLM extraction first; falls back to keyword matching.
        """
        self.graph.clear()
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # Step 1: Add all requirement nodes to graph
        req_dicts = []
        for req in requirements:
            node = GraphNode(
                id=req.id,
                label=req.id,
                type="requirement",
                properties={
                    "text":     req.text[:200] + "..." if len(req.text) > 200 else req.text,
                    "req_type": req.type,
                    "sae_level": req.sae_level,
                    "domain":   req.domain,
                    "tags":     req.tags,
                },
            )
            nodes.append(node)
            self.graph.add_node(req.id, **node.properties, node_type="requirement")
            req_dicts.append({
                "id": req.id, "text": req.text,
                "type": req.type, "sae_level": req.sae_level,
            })

        # Step 2: LLM extraction
        llm_result = extract_graph_from_requirements(req_dicts)
        llm_entities  = llm_result.get("entities", [])
        llm_relations = llm_result.get("relations", [])

        if llm_entities:
            nodes, edges = self._build_from_llm(requirements, nodes, edges, llm_entities, llm_relations)
        else:
            # Fallback: keyword matching
            nodes, edges = self._build_from_keywords(requirements, nodes, edges)

        # Step 3: Ontology backbone (concept → concept edges)
        nodes, edges = self._add_ontology_backbone(nodes, edges)

        return KnowledgeGraph(
            nodes=nodes,
            edges=edges,
            metadata={
                "num_requirements": len(requirements),
                "num_entities": len(nodes) - len(requirements),
                "num_edges":    len(edges),
                "is_dag":       nx.is_directed_acyclic_graph(self.graph),
                "extraction":   "llm" if llm_entities else "keyword",
            },
        )

    def _build_from_llm(self, requirements, nodes, edges, llm_entities, llm_relations):
        # Add LLM-extracted entity nodes
        for ent in llm_entities:
            eid = ent.get("id", "").strip()
            if not eid or eid in self.graph.nodes:
                continue
            etype = ent.get("type", "concept")
            enode = GraphNode(
                id=eid,
                label=ent.get("label", eid),
                type=etype,
                properties={"label": ent.get("label", eid)},
            )
            nodes.append(enode)
            self.graph.add_node(eid, node_type=etype, label=ent.get("label", eid))

        # Add LLM-extracted relations
        existing_ids = set(self.graph.nodes)
        for rel in llm_relations:
            src = rel.get("source", "").strip()
            tgt = rel.get("target", "").strip()
            rtype = rel.get("type", "mentions")
            if src in existing_ids and tgt in existing_ids:
                edge = GraphEdge(source=src, target=tgt, relation=rtype)
                edges.append(edge)
                self.graph.add_edge(src, tgt, relation=rtype)

        # Also scan for explicit REQ-xxx cross-references in text (LLM sometimes misses these)
        req_ids = {r.id for r in requirements}
        for req in requirements:
            refs = re.findall(r"REQ-\d+", req.text, re.IGNORECASE)
            for ref in refs:
                ref_upper = ref.upper()
                if ref_upper != req.id and ref_upper in req_ids:
                    if not self.graph.has_edge(req.id, ref_upper):
                        edge = GraphEdge(source=req.id, target=ref_upper, relation="depends_on")
                        edges.append(edge)
                        self.graph.add_edge(req.id, ref_upper, relation="depends_on")

        return nodes, edges

    # ─── Keyword fallback ─────────────────────────────────────────────────────

    def _build_from_keywords(self, requirements, nodes, edges):
        req_entities: dict[str, list] = {}
        for req in requirements:
            entities = self._extract_entities_kw(req.text)
            req_entities[req.id] = entities
            for ent in entities:
                if ent not in self.graph.nodes:
                    ent_node = GraphNode(
                        id=ent, label=ent,
                        type=self._get_entity_type(ent),
                        properties=PARKING_ONTOLOGY["concepts"].get(ent, {}),
                    )
                    nodes.append(ent_node)
                    self.graph.add_node(ent, node_type=ent_node.type)
                edge = GraphEdge(source=req.id, target=ent, relation="mentions")
                edges.append(edge)
                self.graph.add_edge(req.id, ent, relation="mentions")

        for req in requirements:
            for src, tgt, rel in self._extract_relations_kw(req.id, req.text):
                if tgt in self.graph.nodes and not self.graph.has_edge(src, tgt):
                    edges.append(GraphEdge(source=src, target=tgt, relation=rel))
                    self.graph.add_edge(src, tgt, relation=rel)

        return nodes, edges

    def _extract_entities_kw(self, text: str) -> List[str]:
        found = []
        text_lower = text.lower()
        for concept, keywords in ENTITY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    found.append(concept)
                    break
        return list(set(found))

    def _extract_relations_kw(self, req_id: str, text: str) -> List[Tuple[str, str, str]]:
        edges = []
        text_lower = text.lower()
        refs = re.findall(r"REQ-\d+", text, re.IGNORECASE)
        for ref in refs:
            ref_upper = ref.upper()
            if ref_upper != req_id:
                edges.append((req_id, ref_upper, "depends_on"))
        for rel_type, keywords in DEPENDENCY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    edges.append((req_id, "ONTOLOGY", rel_type))
                    break
        return edges

    # ─── Ontology backbone ────────────────────────────────────────────────────

    def _add_ontology_backbone(self, nodes, edges):
        for src, rel, tgt in PARKING_ONTOLOGY["relations"]:
            if src in self.graph.nodes and tgt in self.graph.nodes:
                if not self.graph.has_edge(src, tgt):
                    edges.append(GraphEdge(source=src, target=tgt, relation=rel))
                    self.graph.add_edge(src, tgt, relation=rel)
        return nodes, edges

    # ─── Traceability + Verification ─────────────────────────────────────────

    def get_traceability(self, req_id: str) -> List[TraceabilityLink]:
        links = []
        if req_id not in self.graph:
            return links
        for pred in self.graph.predecessors(req_id):
            rel = self.graph[pred][req_id].get("relation", "related")
            links.append(TraceabilityLink(
                source_id=pred, target_id=req_id,
                link_type=rel, rationale=f"Upstream {rel}",
            ))
        for succ in self.graph.successors(req_id):
            rel = self.graph[req_id][succ].get("relation", "related")
            links.append(TraceabilityLink(
                source_id=req_id, target_id=succ,
                link_type=rel, rationale=f"Downstream {rel}",
            ))
        return links

    def verify_requirement(self, req: Requirement) -> VerificationResult:
        issues = []
        suggestions = []
        text_lower = req.text.lower()

        if req.sae_level == "L2" and "monitor" not in text_lower:
            issues.append("SAE L2 requirement missing driver monitoring obligation")
            suggestions.append("Add: 'The driver shall continuously monitor the environment'")

        if req.type == "safety" and not any(
            kw in text_lower for kw in ["iso 26262", "asil", "fmea", "sotif", "iso 21448"]
        ):
            issues.append("Safety requirement lacks reference to ISO 26262 / ASIL / SOTIF")
            suggestions.append("Specify the required ASIL level (e.g., ASIL-B or ASIL-D)")

        if req.type == "performance" and not re.search(r"\d+", req.text):
            issues.append("Performance requirement has no quantitative threshold")
            suggestions.append("Add measurable acceptance criterion (e.g., response time ≤ 200ms)")

        ambiguous = ["appropriate", "adequate", "sufficient", "as needed", "if possible"]
        found_ambiguous = [w for w in ambiguous if w in text_lower]
        if found_ambiguous:
            issues.append(f"Ambiguous language: {found_ambiguous}")
            suggestions.append("Replace vague terms with precise, measurable criteria")

        status = "verified" if not issues else ("conflict" if len(issues) > 2 else "incomplete")
        return VerificationResult(
            requirement_id=req.id,
            status=status,
            issues=issues,
            suggestions=suggestions,
        )

    def graph_rag_retrieve(self, query: str, top_k: int = 5):
        query_lower = query.lower()
        scores: dict[str, float] = {}
        for node_id, data in self.graph.nodes(data=True):
            score = 0.0
            text_repr = str(data) + " " + node_id
            for word in query_lower.split():
                if len(word) > 2 and word in text_repr.lower():
                    score += 1.0
            scores[node_id] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        seed_nodes = [n for n, s in ranked[:top_k] if s > 0]

        traversal_path = list(seed_nodes)
        visited = set(seed_nodes)
        for seed in seed_nodes:
            for neighbor in list(self.graph.successors(seed)) + list(self.graph.predecessors(seed)):
                if neighbor not in visited:
                    traversal_path.append(neighbor)
                    visited.add(neighbor)

        return seed_nodes, traversal_path

    def _get_entity_type(self, name: str) -> str:
        concept = PARKING_ONTOLOGY["concepts"].get(name, {})
        parent = concept.get("parent", "")
        if "Sensor" in parent or "Sensor" in name:  return "sensor"
        if "Function" in parent or "Function" in name: return "function"
        if "SafetyLevel" in parent: return "safety_level"
        if "Actor" in parent:       return "actor"
        return "concept"


graph_builder = GraphBuilder()
