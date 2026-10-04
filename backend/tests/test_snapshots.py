"""
Tests for services.state.GraphStore's named snapshots and services.graph_diff
(issue #16): saving/listing in-memory snapshots and diffing two
KnowledgeGraph versions.
"""
import pytest

from models.schemas import KnowledgeGraph, GraphNode, GraphEdge
from services.state import GraphStore
from services import graph_diff


def _graph(nodes, edges=None):
    return KnowledgeGraph(nodes=nodes, edges=edges or [], metadata={})


def test_save_snapshot_requires_a_built_graph():
    store = GraphStore()
    with pytest.raises(ValueError):
        store.save_snapshot("v1")


def test_save_and_list_snapshots():
    store = GraphStore()
    store.graph = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement")])
    store.save_snapshot("v1")

    listed = store.list_snapshots()
    assert len(listed) == 1
    assert listed[0]["name"] == "v1"
    assert listed[0]["node_count"] == 1
    assert listed[0]["edge_count"] == 0


def test_get_snapshot_returns_saved_graph_and_none_when_missing():
    store = GraphStore()
    graph = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement")])
    store.graph = graph
    store.save_snapshot("v1")

    assert store.get_snapshot("v1") is graph
    assert store.get_snapshot("does-not-exist") is None


def test_later_snapshot_unaffected_by_graph_rebuild():
    store = GraphStore()
    store.graph = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement")])
    store.save_snapshot("v1")

    # A later rebuild replaces store.graph wholesale (not mutated in place),
    # so the earlier snapshot's reference must stay untouched.
    store.graph = _graph([GraphNode(id="REQ-2", label="REQ-2", type="requirement")])
    v1 = store.get_snapshot("v1")
    assert [n.id for n in v1.nodes] == ["REQ-1"]


def test_diff_graphs_detects_added_and_removed_nodes():
    a = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement", properties={"text": "old"})])
    b = _graph([
        GraphNode(id="REQ-1", label="REQ-1", type="requirement", properties={"text": "old"}),
        GraphNode(id="REQ-2", label="REQ-2", type="requirement", properties={"text": "new"}),
    ])
    diff = graph_diff.diff_graphs(a, b)
    assert diff["added_nodes"] == ["REQ-2"]
    assert diff["removed_nodes"] == []


def test_diff_graphs_detects_changed_requirement_text():
    a = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement", properties={"text": "old text"})])
    b = _graph([GraphNode(id="REQ-1", label="REQ-1", type="requirement", properties={"text": "new text"})])
    diff = graph_diff.diff_graphs(a, b)
    assert diff["changed_requirements"] == [{"id": "REQ-1", "before": "old text", "after": "new text"}]


def test_diff_graphs_detects_added_and_removed_edges():
    nodes = [
        GraphNode(id="REQ-1", label="REQ-1", type="requirement"),
        GraphNode(id="REQ-2", label="REQ-2", type="requirement"),
    ]
    a = _graph(nodes, [])
    b = _graph(nodes, [GraphEdge(source="REQ-1", target="REQ-2", relation="depends_on")])
    diff = graph_diff.diff_graphs(a, b)
    assert diff["added_edges"] == [{"source": "REQ-1", "target": "REQ-2", "relation": "depends_on"}]
    assert diff["removed_edges"] == []


def test_diff_graphs_identical_snapshots_is_empty_diff():
    nodes = [GraphNode(id="REQ-1", label="REQ-1", type="requirement", properties={"text": "same"})]
    a = _graph(nodes)
    b = _graph(nodes)
    diff = graph_diff.diff_graphs(a, b)
    assert diff == {
        "added_nodes": [],
        "removed_nodes": [],
        "added_edges": [],
        "removed_edges": [],
        "changed_requirements": [],
    }
