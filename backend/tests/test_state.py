"""
Tests for backend/services/state.py's GraphStore (issue #17).

set_graph used to clear self.requirements before repopulating it from the
build batch, silently dropping any requirement added separately via
POST /requirements or POST /requirements/batch that wasn't part of that
batch. It should merge instead.
"""
from models.schemas import KnowledgeGraph, Requirement
from services.state import GraphStore


def _graph():
    return KnowledgeGraph(nodes=[], edges=[], metadata={})


def test_set_graph_preserves_requirements_added_outside_the_batch():
    store = GraphStore()

    # Added separately via POST /requirements, not part of any build batch.
    extra = Requirement(id="REQ-EXTRA", text="Added out of band.", type="functional")
    store.requirements[extra.id] = extra

    batch_req = Requirement(id="REQ-BATCH", text="From the build batch.", type="functional")
    store.set_graph(_graph(), [batch_req])

    assert "REQ-EXTRA" in store.requirements
    assert "REQ-BATCH" in store.requirements


def test_set_graph_updates_requirement_with_same_id():
    store = GraphStore()
    old = Requirement(id="REQ-1", text="Old text.", type="functional")
    store.requirements[old.id] = old

    new = Requirement(id="REQ-1", text="New text.", type="functional")
    store.set_graph(_graph(), [new])

    assert store.requirements["REQ-1"].text == "New text."


def test_set_graph_sets_the_graph():
    store = GraphStore()
    graph = _graph()
    store.set_graph(graph, [])
    assert store.graph is graph
