"""Shared in-memory state (issue #6): one place instead of cross-router globals."""
import threading
import time
from models.schemas import KnowledgeGraph, Requirement


class GraphStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.graph: KnowledgeGraph | None = None
        self.requirements: dict[str, Requirement] = {}
        # name -> {"graph": KnowledgeGraph, "created_at": epoch float} (issue #16)
        # In-memory only, same singleton/per-process caveats as the rest of
        # this store (issue #6) — snapshots don't survive a restart.
        self.snapshots: dict[str, dict] = {}

    def set_graph(self, graph: KnowledgeGraph, requirements) -> None:
        """Set the current graph and merge in the batch's requirements.

        Previously this cleared self.requirements before repopulating from
        the batch, which silently dropped any requirement added separately
        via POST /requirements (or /requirements/batch) that wasn't part of
        this build batch (issue #17). Merge instead, so a graph rebuild
        never erases requirements added through other endpoints.
        """
        with self.lock_ctx():
            self.graph = graph
            self.requirements.update({r.id: r for r in requirements})

    def lock_ctx(self):
        return self._lock

    def save_snapshot(self, name: str) -> dict:
        """Save a named point-in-time copy of the current graph (issue #16).
        Stores a reference to the current KnowledgeGraph, which is itself
        replaced (not mutated) on every /graph/build, so existing snapshots
        stay intact across later rebuilds."""
        if self.graph is None:
            raise ValueError("No graph built yet")
        with self.lock_ctx():
            snapshot = {"graph": self.graph, "created_at": time.time()}
            self.snapshots[name] = snapshot
            return snapshot

    def list_snapshots(self) -> list[dict]:
        return [
            {
                "name": name,
                "created_at": snap["created_at"],
                "node_count": len(snap["graph"].nodes),
                "edge_count": len(snap["graph"].edges),
            }
            for name, snap in sorted(self.snapshots.items(), key=lambda kv: kv[1]["created_at"])
        ]

    def get_snapshot(self, name: str) -> KnowledgeGraph | None:
        snap = self.snapshots.get(name)
        return snap["graph"] if snap else None


store = GraphStore()


def get_store() -> GraphStore:
    return store
