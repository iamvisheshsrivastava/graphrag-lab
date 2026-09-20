"""Shared in-memory state (issue #6): one place instead of cross-router globals."""
import threading
from models.schemas import KnowledgeGraph, Requirement


class GraphStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.graph: KnowledgeGraph | None = None
        self.requirements: dict[str, Requirement] = {}

    def set_graph(self, graph: KnowledgeGraph, requirements) -> None:
        with self.lock_ctx():
            self.graph = graph
            self.requirements.clear()
            self.requirements.update({r.id: r for r in requirements})

    def lock_ctx(self):
        return self._lock


store = GraphStore()


def get_store() -> GraphStore:
    return store
