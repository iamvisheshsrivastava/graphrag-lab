"""
Knowledge Graph Builder for automotive parking requirements.

Builds a deterministic knowledge graph from structured requirements using:
- Ontology-guided entity extraction
- Dependency analysis
- Traceability link generation
"""

import re
import networkx as nx
from typing import List, Tuple
from models.schemas import (
    Requirement, KnowledgeGraph, GraphNode, GraphEdge, TraceabilityLink, VerificationResult
)
from services.ontology import PARKING_ONTOLOGY, ALL_CONCEPTS


# ─── Keyword maps for deterministic entity extraction ────────────────────────

ENTITY_KEYWORDS = {
    "UltrasonicSensor": ["ultrasonic", "USS", "proximity sensor"],
    "Camera": ["camera", "vision", "image"],
    "Camera360": ["surround view", "360", "bird-eye"],
    "Radar": ["radar", "FMCW"],
    "LiDAR": ["lidar", "laser"],
    "Driver": ["driver", "operator", "user"],
    "Pedestrian": ["pedestrian", "person", "cyclist"],
    "ParkingSpace": ["parking space", "slot", "bay"],
    "RemoteParkingAssist": ["remote parking", "RPA"],
    "AutomaticParkingAssist": ["APA", "automatic park", "auto park"],
    "SummonFunction": ["summon", "home-to-me"],
    "ASIL_B": ["ASIL-B", "ASIL B"],
    "ASIL_D": ["ASIL-D", "ASIL D"],
    "ISO26262": ["ISO 26262", "ISO26262", "functional safety"],
}

DEPENDENCY_KEYWORDS = {
    "depends_on": ["depends on", "requires", "needs", "shall use", "must use"],
    "refines": ["refines", "specializes", "is a type of"],
    "conflicts_with": ["conflicts with", "contradicts", "mutually exclusive"],
    "derives_from": ["derived from", "allocated to", "traces to"],
    "implements": ["implements", "realizes", "satisfies"],
}


class GraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def _extract_entities(self, text: str) -> List[str]:
        """Deterministically extract ontology concepts from requirement text."""
        found = []
        text_lower = text.lower()
        for concept, keywords in ENTITY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    found.append(concept)
                    break
        return list(set(found))

    def _extract_relations(self, req_id: str, text: str) -> List[Tuple[str, str, str]]:
        """Extract dependency relations between requirements."""
        edges = []
        text_lower = text.lower()

        # Detect references to other requirement IDs (e.g., REQ-001)
        refs = re.findall(r"REQ-\d+", text, re.IGNORECASE)
        for ref in refs:
            ref_upper = ref.upper()
            if ref_upper != req_id:
                edges.append((req_id, ref_upper, "depends_on"))

        # Detect semantic dependency keywords
        for rel_type, keywords in DEPENDENCY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    edges.append((req_id, "ONTOLOGY", rel_type))
                    break

        return edges

    def build_from_requirements(self, requirements: List[Requirement]) -> KnowledgeGraph:
        """Build a knowledge graph from a list of requirements."""
        self.graph.clear()
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # 1. Add requirement nodes
        for req in requirements:
            node = GraphNode(
                id=req.id,
                label=req.id,
                type="requirement",
                properties={
                    "text": req.text[:120] + "..." if len(req.text) > 120 else req.text,
                    "req_type": req.type,
                    "sae_level": req.sae_level,
                    "domain": req.domain,
                    "tags": req.tags,
                },
            )
            nodes.append(node)
            self.graph.add_node(req.id, **node.properties, node_type="requirement")

        # 2. Extract ontology entities and add as nodes
        req_entities: dict[str, list] = {}
        for req in requirements:
            entities = self._extract_entities(req.text)
            req_entities[req.id] = entities
            for ent in entities:
                if ent not in self.graph.nodes:
                    ent_node = GraphNode(
                        id=ent,
                        label=ent,
                        type=self._get_entity_type(ent),
                        properties=PARKING_ONTOLOGY["concepts"].get(ent, {}),
                    )
                    nodes.append(ent_node)
                    self.graph.add_node(ent, node_type=ent_node.type)

                # Edge: requirement → entity (mentions)
                edge = GraphEdge(source=req.id, target=ent, relation="mentions")
                edges.append(edge)
                self.graph.add_edge(req.id, ent, relation="mentions")

        # 3. Extract requirement-to-requirement relations
        for req in requirements:
            rel_edges = self._extract_relations(req.id, req.text)
            for src, tgt, rel in rel_edges:
                if tgt in self.graph.nodes:
                    edge = GraphEdge(source=src, target=tgt, relation=rel)
                    edges.append(edge)
                    self.graph.add_edge(src, tgt, relation=rel)

        # 4. Add ontology backbone edges (concept → concept)
        for src, rel, tgt in PARKING_ONTOLOGY["relations"]:
            if src in self.graph.nodes and tgt in self.graph.nodes:
                edge = GraphEdge(source=src, target=tgt, relation=rel)
                edges.append(edge)
                self.graph.add_edge(src, tgt, relation=rel)

        return KnowledgeGraph(
            nodes=nodes,
            edges=edges,
            metadata={
                "num_requirements": len(requirements),
                "num_entities": len(nodes) - len(requirements),
                "num_edges": len(edges),
                "is_dag": nx.is_directed_acyclic_graph(self.graph),
            },
        )

    def get_traceability(self, req_id: str) -> List[TraceabilityLink]:
        """Return all traceability links for a requirement (upstream + downstream)."""
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
        """
        Deterministic rule-based verification of a requirement.
        Checks ontology consistency and safety constraints.
        """
        issues = []
        suggestions = []

        text_lower = req.text.lower()

        # Rule 1: L2 functions must mention driver monitoring
        if req.sae_level == "L2" and "monitor" not in text_lower:
            issues.append("SAE L2 requirement missing driver monitoring obligation")
            suggestions.append("Add: 'The driver shall continuously monitor the environment'")

        # Rule 2: Safety requirements must reference a safety standard
        if req.type == "safety" and not any(
            kw in text_lower for kw in ["iso 26262", "asil", "fmea"]
        ):
            issues.append("Safety requirement lacks reference to ISO 26262 or ASIL level")
            suggestions.append("Specify the required ASIL level (e.g., ASIL-B or ASIL-D)")

        # Rule 3: Performance requirements must be quantifiable
        if req.type == "performance" and not re.search(r"\d+", req.text):
            issues.append("Performance requirement has no quantitative threshold")
            suggestions.append("Add measurable acceptance criterion (e.g., response time ≤ 200ms)")

        # Rule 4: Ambiguity check
        ambiguous = ["appropriate", "adequate", "sufficient", "as needed", "if possible"]
        found_ambiguous = [w for w in ambiguous if w in text_lower]
        if found_ambiguous:
            issues.append(f"Ambiguous language detected: {found_ambiguous}")
            suggestions.append("Replace vague terms with precise, measurable criteria")

        status = "verified" if not issues else ("conflict" if len(issues) > 2 else "incomplete")
        return VerificationResult(
            requirement_id=req.id,
            status=status,
            issues=issues,
            suggestions=suggestions,
        )

    def graph_rag_retrieve(self, query: str, top_k: int = 5):
        """
        Graph-guided retrieval: find nodes most relevant to the query,
        then expand via graph traversal to collect context.
        Returns (relevant_nodes, traversal_path).
        """
        query_lower = query.lower()
        scores: dict[str, float] = {}

        # Score nodes by keyword overlap
        for node_id, data in self.graph.nodes(data=True):
            score = 0.0
            text_repr = str(data) + " " + node_id
            for word in query_lower.split():
                if word in text_repr.lower():
                    score += 1.0
            scores[node_id] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        seed_nodes = [n for n, s in ranked[:top_k] if s > 0]

        # BFS expansion up to depth 2
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
        if "Sensor" in parent or "Sensor" in name:
            return "sensor"
        if "Function" in parent or "Function" in name:
            return "function"
        if "Requirement" in parent:
            return "requirement_type"
        if "SafetyLevel" in parent:
            return "safety_level"
        if "Actor" in parent:
            return "actor"
        return "concept"


# Singleton instance
graph_builder = GraphBuilder()
