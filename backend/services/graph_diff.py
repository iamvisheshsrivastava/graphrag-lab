"""
Diff two KnowledgeGraph snapshots (issue #16) — plain set operations over
node/edge ids, plus a text-change check for requirement nodes that share an
id across both snapshots.
"""

from models.schemas import KnowledgeGraph


def diff_graphs(a: KnowledgeGraph, b: KnowledgeGraph) -> dict:
    """Returns added/removed nodes, added/removed edges, and requirement
    nodes whose text changed between snapshot `a` (older) and `b` (newer)."""
    a_nodes = {n.id: n for n in a.nodes}
    b_nodes = {n.id: n for n in b.nodes}
    a_edges = {(e.source, e.target, e.relation) for e in a.edges}
    b_edges = {(e.source, e.target, e.relation) for e in b.edges}

    added_nodes = sorted(set(b_nodes) - set(a_nodes))
    removed_nodes = sorted(set(a_nodes) - set(b_nodes))

    added_edges = [
        {"source": s, "target": t, "relation": r}
        for s, t, r in sorted(b_edges - a_edges)
    ]
    removed_edges = [
        {"source": s, "target": t, "relation": r}
        for s, t, r in sorted(a_edges - b_edges)
    ]

    changed_requirements = []
    for node_id in set(a_nodes) & set(b_nodes):
        na, nb = a_nodes[node_id], b_nodes[node_id]
        if na.type == "requirement" and nb.type == "requirement":
            text_a = na.properties.get("text", "")
            text_b = nb.properties.get("text", "")
            if text_a != text_b:
                changed_requirements.append({"id": node_id, "before": text_a, "after": text_b})
    changed_requirements.sort(key=lambda c: c["id"])

    return {
        "added_nodes": added_nodes,
        "removed_nodes": removed_nodes,
        "added_edges": added_edges,
        "removed_edges": removed_edges,
        "changed_requirements": changed_requirements,
    }
