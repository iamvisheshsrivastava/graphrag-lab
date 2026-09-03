"""
Tests for services.graph_builder — the deterministic ontology-resolution and
verification logic (issue #7). These are pure/offline: LLM extraction is
forced off via monkeypatch so the keyword-fallback + ontology-backbone path
runs deterministically, with no network calls.
"""
import pytest

from models.schemas import Requirement
import services.graph_builder as gb_module
from services.graph_builder import GraphBuilder


@pytest.fixture
def builder(monkeypatch):
    # Force the keyword-fallback path regardless of whether OPENROUTER_API_KEY
    # / OPENAI_API_KEY happen to be set in the environment running the tests.
    monkeypatch.setattr(
        gb_module, "extract_graph_from_requirements", lambda reqs: {"entities": [], "relations": []}
    )
    return GraphBuilder()


# ─── verify_requirement ─────────────────────────────────────────────────────

def test_verify_requirement_clean_passes(builder):
    req = Requirement(
        id="REQ-001",
        text="The system shall detect obstacles within 200ms using ultrasonic sensors per ISO 26262 ASIL-B.",
        type="safety",
        sae_level="L2",
        domain="parking",
    )
    result = builder.verify_requirement(req)
    # Safety keyword present, but L2 requires "monitor" language too.
    assert "SAE L2 requirement missing driver monitoring obligation" in result.issues


def test_verify_requirement_l2_missing_monitor(builder):
    req = Requirement(id="REQ-002", text="The system shall park the vehicle.", sae_level="L2")
    result = builder.verify_requirement(req)
    assert any("driver monitoring" in i for i in result.issues)


def test_verify_requirement_safety_missing_standard_ref(builder):
    req = Requirement(id="REQ-003", text="The system shall be safe.", type="safety", sae_level="L1")
    result = builder.verify_requirement(req)
    assert any("ISO 26262" in i for i in result.issues)


def test_verify_requirement_performance_missing_threshold(builder):
    req = Requirement(
        id="REQ-004", text="The system shall respond quickly.", type="performance", sae_level="L1"
    )
    result = builder.verify_requirement(req)
    assert any("quantitative threshold" in i for i in result.issues)


def test_verify_requirement_ambiguous_language_flagged(builder):
    req = Requirement(
        id="REQ-005",
        text="The driver shall monitor the environment with adequate attention.",
        sae_level="L2",
    )
    result = builder.verify_requirement(req)
    assert any("Ambiguous language" in i for i in result.issues)


def test_verify_requirement_fully_clean_is_verified(builder):
    req = Requirement(
        id="REQ-006",
        text=(
            "The driver shall continuously monitor the environment while the system "
            "responds within 200ms per ISO 26262 ASIL-B."
        ),
        type="safety",
        sae_level="L2",
    )
    result = builder.verify_requirement(req)
    assert result.status == "verified"
    assert result.issues == []


# ─── keyword extraction + ontology backbone ─────────────────────────────────

def test_build_from_requirements_keyword_fallback_extracts_entities(builder):
    reqs = [
        Requirement(
            id="REQ-010",
            text="The system shall use an ultrasonic sensor to detect obstacles near the parking space.",
            type="functional",
            sae_level="L2",
        )
    ]
    graph = builder.build_from_requirements(reqs)
    assert graph.metadata["extraction"] == "keyword"

    node_ids = {n.id for n in graph.nodes}
    assert "UltrasonicSensor" in node_ids
    assert "ParkingSpace" in node_ids

    # Ontology backbone: (UltrasonicSensor, detects, ParkingSpace) should now
    # resolve since both concrete nodes exist in the graph (issue #9 fix).
    backbone_edges = [
        (e.source, e.target, e.relation) for e in graph.edges if e.relation == "detects"
    ]
    assert ("UltrasonicSensor", "ParkingSpace", "detects") in backbone_edges


def test_resolve_ontology_endpoint_concrete_id(builder):
    builder.graph.add_node("UltrasonicSensor", node_type="sensor")
    assert builder._resolve_ontology_endpoint("UltrasonicSensor") == ["UltrasonicSensor"]


def test_resolve_ontology_endpoint_requirement_type_category(builder):
    builder.graph.add_node("REQ-001", node_type="requirement", req_type="safety")
    builder.graph.add_node("REQ-002", node_type="requirement", req_type="functional")
    resolved = builder._resolve_ontology_endpoint("SafetyRequirement")
    assert resolved == ["REQ-001"]


def test_resolve_ontology_endpoint_abstract_parent_category(builder):
    # "UltrasonicSensor"'s ontology parent is "Sensor" (see PARKING_ONTOLOGY).
    builder.graph.add_node("UltrasonicSensor", node_type="sensor")
    builder.graph.add_node("Driver", node_type="actor")  # unrelated, parent HumanActor
    resolved = builder._resolve_ontology_endpoint("Sensor")
    assert resolved == ["UltrasonicSensor"]


def test_resolve_ontology_endpoint_unresolvable_returns_empty(builder):
    assert builder._resolve_ontology_endpoint("NotARealCategory") == []


def test_get_traceability_returns_upstream_and_downstream(builder):
    builder.graph.add_node("REQ-A", node_type="requirement")
    builder.graph.add_node("REQ-B", node_type="requirement")
    builder.graph.add_edge("REQ-A", "REQ-B", relation="depends_on")

    links = builder.get_traceability("REQ-B")
    assert any(l.source_id == "REQ-A" and l.target_id == "REQ-B" for l in links)

    links_a = builder.get_traceability("REQ-A")
    assert any(l.source_id == "REQ-A" and l.target_id == "REQ-B" for l in links_a)


def test_get_traceability_unknown_node_returns_empty(builder):
    assert builder.get_traceability("does-not-exist") == []
