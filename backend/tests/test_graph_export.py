"""
Tests for services.graph_export — GraphML/Cypher/JSON-LD serialization of
the current knowledge graph (issue #14).
"""
import json

from models.schemas import KnowledgeGraph, GraphNode, GraphEdge
from services import graph_export


def _sample_graph():
    return KnowledgeGraph(
        nodes=[
            GraphNode(
                id="REQ-1", label="REQ-1", type="requirement",
                properties={
                    "text": "The system shall park within 10s.",
                    "req_type": "functional", "sae_level": "L2",
                    "domain": "parking", "tags": ["a", "b"],
                },
            ),
            GraphNode(
                id="UltrasonicSensor", label="UltrasonicSensor", type="sensor",
                properties={"label": "UltrasonicSensor"},
            ),
        ],
        edges=[GraphEdge(source="REQ-1", target="UltrasonicSensor", relation="uses")],
        metadata={"num_requirements": 1},
    )


def test_flatten_properties_handles_list_and_none_values():
    flat = graph_export._flatten_properties({"tags": ["a", "b"], "domain": "parking", "empty": None})
    assert flat["tags"] == json.dumps(["a", "b"])
    assert flat["domain"] == "parking"
    assert "empty" not in flat


def test_to_graphml_contains_nodes_and_edges():
    xml = graph_export.to_graphml(_sample_graph())
    assert "<graphml" in xml
    assert "REQ-1" in xml
    assert "UltrasonicSensor" in xml


def test_to_cypher_contains_merge_and_relation_statements():
    script = graph_export.to_cypher(_sample_graph())
    assert "MERGE" in script
    assert ":Requirement" in script
    assert ":Entity" in script
    assert ":USES" in script


def test_to_jsonld_has_context_and_both_nodes():
    doc = graph_export.to_jsonld(_sample_graph())
    assert "@context" in doc
    assert "@graph" in doc
    ids = [n["@id"] for n in doc["@graph"] if "@id" in n]
    assert "REQ-1" in ids
    assert "UltrasonicSensor" in ids


def test_to_jsonld_includes_edge_as_graph_item():
    doc = graph_export.to_jsonld(_sample_graph())
    edge_items = [n for n in doc["@graph"] if n.get("@type") == "uses"]
    assert len(edge_items) == 1
    assert edge_items[0]["source"] == "REQ-1"
    assert edge_items[0]["target"] == "UltrasonicSensor"
