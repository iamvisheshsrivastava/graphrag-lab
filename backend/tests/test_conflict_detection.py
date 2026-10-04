"""
Tests for GraphBuilder.detect_conflicts — the deterministic conflict
detection pass added for issue #15 (explicit conflicts_with edges, numeric
threshold mismatches, ASIL mismatches).
"""
from models.schemas import Requirement
from services.graph_builder import GraphBuilder


def test_detects_explicit_conflicts_with_edge():
    gb = GraphBuilder()
    gb.graph.add_node("REQ-1", node_type="requirement")
    gb.graph.add_node("REQ-2", node_type="requirement")
    gb.graph.add_edge("REQ-1", "REQ-2", relation="conflicts_with")

    conflicts = gb.detect_conflicts({})
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "explicit_conflicts_with"
    assert {conflicts[0].requirement_a, conflicts[0].requirement_b} == {"REQ-1", "REQ-2"}


def test_detects_numeric_mismatch_on_depends_on_edge():
    gb = GraphBuilder()
    r1 = Requirement(id="REQ-1", text="The parking maneuver shall complete within 10s.")
    r2 = Requirement(id="REQ-2", text="The maneuver shall complete within 15s.")
    gb.graph.add_node("REQ-1", node_type="requirement")
    gb.graph.add_node("REQ-2", node_type="requirement")
    gb.graph.add_edge("REQ-1", "REQ-2", relation="depends_on")

    conflicts = gb.detect_conflicts({"REQ-1": r1, "REQ-2": r2})
    numeric = [c for c in conflicts if c.conflict_type == "numeric_mismatch"]
    assert len(numeric) == 1


def test_detects_asil_mismatch_on_depends_on_edge():
    gb = GraphBuilder()
    r1 = Requirement(id="REQ-1", text="Safety function requires ASIL-D.", type="safety")
    r2 = Requirement(id="REQ-2", text="Sub-function requires ASIL-B.", type="safety")
    gb.graph.add_node("REQ-1", node_type="requirement")
    gb.graph.add_node("REQ-2", node_type="requirement")
    gb.graph.add_edge("REQ-1", "REQ-2", relation="depends_on")

    conflicts = gb.detect_conflicts({"REQ-1": r1, "REQ-2": r2})
    asil = [c for c in conflicts if c.conflict_type == "asil_mismatch"]
    assert len(asil) == 1
    assert asil[0].requirement_a == "REQ-1"
    assert asil[0].requirement_b == "REQ-2"


def test_no_conflicts_for_matching_requirements():
    gb = GraphBuilder()
    r1 = Requirement(id="REQ-1", text="The maneuver shall complete within 10s.")
    r2 = Requirement(id="REQ-2", text="The maneuver shall complete within 10s.")
    gb.graph.add_node("REQ-1", node_type="requirement")
    gb.graph.add_node("REQ-2", node_type="requirement")
    gb.graph.add_edge("REQ-1", "REQ-2", relation="depends_on")

    assert gb.detect_conflicts({"REQ-1": r1, "REQ-2": r2}) == []


def test_ignores_edges_to_non_requirement_entities():
    gb = GraphBuilder()
    r1 = Requirement(id="REQ-1", text="The system shall use an ultrasonic sensor within 10s.")
    gb.graph.add_node("REQ-1", node_type="requirement")
    gb.graph.add_node("UltrasonicSensor", node_type="sensor")
    gb.graph.add_edge("REQ-1", "UltrasonicSensor", relation="depends_on")

    # Only REQ-1 is in the requirements dict; UltrasonicSensor is an entity,
    # not a requirement, so no numeric/ASIL comparison should be attempted.
    assert gb.detect_conflicts({"REQ-1": r1}) == []
