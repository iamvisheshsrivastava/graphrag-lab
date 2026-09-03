"""
Neo4j AuraDB integration for GraphRAG Lab.

Stores the knowledge graph in Neo4j so it can be queried via Cypher.
Falls back gracefully if Neo4j is not configured.

Node labels:
    :Requirement  { id, text, type, sae_level, domain }
    :Entity       { id, label, entity_type }

Relationships:
    (:Requirement)-[:MENTIONS]->(:Entity)
    (:Requirement)-[:DEPENDS_ON]->(:Requirement)
    (:Requirement)-[:DERIVES_FROM]->(:Entity)
    (:Requirement)-[:CONFLICTS_WITH]->(:Requirement)
    (:Requirement)-[:REFINES]->(:Requirement)
    (:Requirement)-[:IMPLEMENTS]->(:Entity)
    (:Entity)-[:PART_OF|:USES|:GOVERNED_BY|:CONNECTED_TO]->(:Entity)
"""

import os
import logging
from collections import defaultdict
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy import — only fails at connection time, not import time
try:
    from neo4j import GraphDatabase, READ_ACCESS, exceptions as neo4j_exc
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed — graph persistence disabled")

# Allowlist of relationship types we ever write. `run_cypher` uses this to
# reject writes at the app layer too (defense in depth), and `persist_graph`
# uses it as the sole source of the relationship type interpolated into
# Cypher strings — never pass an unvalidated string into the f-string below.
REL_MAP = {
    "mentions":       "MENTIONS",
    "depends_on":     "DEPENDS_ON",
    "derives_from":   "DERIVES_FROM",
    "conflicts_with": "CONFLICTS_WITH",
    "refines":        "REFINES",
    "implements":     "IMPLEMENTS",
    "part_of":        "PART_OF",
    "uses":           "USES",
    "governed_by":    "GOVERNED_BY",
    "connected_to":   "CONNECTED_TO",
}


def _driver():
    uri  = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        return None
    return GraphDatabase.driver(uri, auth=(user, pwd))


# ─── Write ────────────────────────────────────────────────────────────────────

def ensure_constraints() -> None:
    """
    Create id-uniqueness constraints, scoped per label, so a :Requirement and
    an :Entity can never collide on the same id value. Idempotent — safe to
    call on every startup. This is what makes the label-filtered MATCH in
    _write_graph_tx() below actually sound (see issue #10).
    """
    if not NEO4J_AVAILABLE:
        return
    driver = _driver()
    if driver is None:
        return
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            session.run(
                "CREATE CONSTRAINT requirement_id_unique IF NOT EXISTS "
                "FOR (r:Requirement) REQUIRE r.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
            )
        logger.info("Neo4j uniqueness constraints ensured")
    except Exception as e:
        logger.error("Neo4j constraint setup error: %s", e)
    finally:
        driver.close()


def _write_graph_tx(tx, graph_data: dict) -> None:
    """Runs inside a single execute_write transaction — batched with UNWIND
    instead of one round-trip per node/edge, and label-filtered edge MATCHes
    so an id collision between a :Requirement and an :Entity can't produce a
    Cartesian-product write (see issues #5 and #10)."""
    nodes = graph_data.get("nodes", [])
    id_to_label: dict = {}

    req_rows = []
    entity_rows = []
    for node in nodes:
        if node["type"] == "requirement":
            id_to_label[node["id"]] = "Requirement"
            req_rows.append({
                "id": node["id"],
                "label": node.get("label", node["id"]),
                "text": node.get("properties", {}).get("text", ""),
                "req_type": node.get("properties", {}).get("req_type", ""),
                "sae_level": node.get("properties", {}).get("sae_level", ""),
                "domain": node.get("properties", {}).get("domain", ""),
            })
        else:
            id_to_label[node["id"]] = "Entity"
            entity_rows.append({
                "id": node["id"],
                "label": node.get("label", node["id"]),
                "entity_type": node["type"],
            })

    if req_rows:
        tx.run(
            """
            UNWIND $rows AS row
            MERGE (r:Requirement {id: row.id})
            SET r.label     = row.label,
                r.text      = row.text,
                r.req_type  = row.req_type,
                r.sae_level = row.sae_level,
                r.domain    = row.domain
            """,
            rows=req_rows,
        )

    if entity_rows:
        tx.run(
            """
            UNWIND $rows AS row
            MERGE (e:Entity {id: row.id})
            SET e.label       = row.label,
                e.entity_type = row.entity_type
            """,
            rows=entity_rows,
        )

    # Group edges by (source label, target label, relationship type) so each
    # group can be written with one UNWIND. Labels default to Entity when a
    # node wasn't in this batch (defensive — shouldn't normally happen).
    grouped = defaultdict(list)
    for edge in graph_data.get("edges", []):
        rel = REL_MAP.get(edge["relation"], "RELATED_TO")
        src_label = id_to_label.get(edge["source"], "Entity")
        tgt_label = id_to_label.get(edge["target"], "Entity")
        grouped[(src_label, tgt_label, rel)].append(
            {"src": edge["source"], "tgt": edge["target"]}
        )

    for (src_label, tgt_label, rel), pairs in grouped.items():
        # rel is only ever a REL_MAP value or the literal "RELATED_TO" —
        # never an unvalidated caller-supplied string — so this f-string is safe.
        cypher = f"""
            UNWIND $pairs AS pair
            MATCH (a:{src_label} {{id: pair.src}}), (b:{tgt_label} {{id: pair.tgt}})
            MERGE (a)-[:{rel}]->(b)
        """
        tx.run(cypher, pairs=pairs)


def persist_graph(graph_data: dict) -> bool:
    """
    Write KnowledgeGraph nodes + edges to Neo4j.
    Idempotent — MERGE ensures no duplicates on rebuild.
    Returns True on success, False if Neo4j is unavailable.
    """
    if not NEO4J_AVAILABLE:
        return False
    driver = _driver()
    if driver is None:
        return False

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            # Clear only this app's data — not the whole database, in case the
            # AuraDB instance is ever shared with anything else (see issue #5).
            session.run("MATCH (n) WHERE n:Requirement OR n:Entity DETACH DELETE n")

            # Single write transaction, batched with UNWIND (see issue #5).
            session.execute_write(_write_graph_tx, graph_data)

        logger.info("Graph persisted to Neo4j AuraDB (%d nodes, %d edges)",
                    len(graph_data.get("nodes", [])),
                    len(graph_data.get("edges", [])))
        return True

    except Exception as e:
        logger.error("Neo4j persist error: %s", e)
        return False
    finally:
        driver.close()


# ─── Cypher Query ─────────────────────────────────────────────────────────────

def run_cypher(query: str, params: Optional[dict] = None) -> dict:
    """
    Execute a read-only Cypher query against Neo4j.

    Enforced read-only by opening the session/transaction in READ_ACCESS mode
    (session.execute_read) — the Neo4j driver attaches that access mode to
    the transaction metadata and the server itself rejects any write clause
    (CREATE/MERGE/DELETE/SET/DROP/...) with a ClientError. This is real
    enforcement, not string/keyword pattern matching, which is easy to evade.

    Returns { columns, rows, row_count } or { error }.
    """
    if not NEO4J_AVAILABLE:
        return {"error": "Neo4j is not available."}
    driver = _driver()
    if driver is None:
        return {"error": "Neo4j is not configured."}

    def _read_tx(tx):
        result = tx.run(query, **(params or {}))
        records = result.data()
        columns = list(records[0].keys()) if records else []
        # Serialize neo4j Node/Relationship objects to plain dicts
        rows = [_serialize_record(r) for r in records]
        return {"columns": columns, "rows": rows, "row_count": len(rows)}

    try:
        with driver.session(
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            default_access_mode=READ_ACCESS,
        ) as session:
            return session.execute_read(_read_tx)
    except Exception as e:
        # Log the real driver error server-side; never echo it to the client
        # (it can contain internal URIs/messages) — see issue #7.
        logger.error("Cypher query error: %s", e)
        return {
            "error": (
                "Query failed. This endpoint is read-only — write clauses "
                "(CREATE/MERGE/DELETE/SET/DROP/etc.) are rejected. The query "
                "may also contain a syntax error."
            )
        }
    finally:
        driver.close()


def _serialize_record(record: dict) -> dict:
    out = {}
    for k, v in record.items():
        if hasattr(v, "_properties"):          # neo4j Node / Relationship
            out[k] = dict(v._properties)
            if hasattr(v, "labels"):
                out[k]["_labels"] = list(v.labels)
        elif hasattr(v, "type"):               # Relationship
            out[k] = {"type": v.type, **dict(v._properties)}
        else:
            out[k] = v
    return out


# ─── Reload (startup) ─────────────────────────────────────────────────────────

# Inverse of REL_MAP — Cypher relationship type -> the lowercase relation
# name the rest of the app (GraphEdge.relation) uses.
_INV_REL_MAP = {v: k for k, v in REL_MAP.items()}


def load_graph() -> Optional[dict]:
    """
    Reload the most recently persisted graph from Neo4j into the
    KnowledgeGraph dict shape (nodes/edges/metadata) used elsewhere in the
    app. Returns None if Neo4j isn't configured/available, on any query
    error, or if there's simply no data yet (fresh database).

    This implements the startup half of issue #6: on process restart (the
    common case on Render free tier), the in-memory NetworkX graph is empty
    but Neo4j — if configured — still has the last-built graph, so we can
    repopulate `_current_graph` without requiring the user to rebuild.
    Requirement objects (`_current_requirements`) are not reconstructed —
    nothing currently reads that list back out (see routers/graph.py).
    """
    if not NEO4J_AVAILABLE:
        return None
    driver = _driver()
    if driver is None:
        return None

    try:
        with driver.session(
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            default_access_mode=READ_ACCESS,
        ) as session:
            def _read(tx):
                req_rows = tx.run(
                    "MATCH (r:Requirement) RETURN r.id AS id, r.label AS label, "
                    "r.text AS text, r.req_type AS req_type, "
                    "r.sae_level AS sae_level, r.domain AS domain"
                ).data()
                entity_rows = tx.run(
                    "MATCH (e:Entity) RETURN e.id AS id, e.label AS label, "
                    "e.entity_type AS entity_type"
                ).data()
                edge_rows = tx.run(
                    "MATCH (a)-[rel]->(b) "
                    "WHERE (a:Requirement OR a:Entity) AND (b:Requirement OR b:Entity) "
                    "RETURN a.id AS source, b.id AS target, type(rel) AS rel_type"
                ).data()
                return req_rows, entity_rows, edge_rows

            req_rows, entity_rows, edge_rows = session.execute_read(_read)

        if not req_rows and not entity_rows:
            return None  # nothing persisted yet

        nodes = []
        for row in req_rows:
            nodes.append({
                "id": row["id"],
                "label": row.get("label") or row["id"],
                "type": "requirement",
                "properties": {
                    "text": row.get("text") or "",
                    "req_type": row.get("req_type") or "",
                    "sae_level": row.get("sae_level") or "",
                    "domain": row.get("domain") or "",
                },
            })
        for row in entity_rows:
            nodes.append({
                "id": row["id"],
                "label": row.get("label") or row["id"],
                "type": row.get("entity_type") or "concept",
                "properties": {"label": row.get("label") or row["id"]},
            })

        edges = [
            {
                "source": row["source"],
                "target": row["target"],
                "relation": _INV_REL_MAP.get(row["rel_type"], row["rel_type"].lower()),
            }
            for row in edge_rows
        ]

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "num_requirements": len(req_rows),
                "num_entities": len(entity_rows),
                "num_edges": len(edges),
                "extraction": "neo4j-reload",
            },
        }

    except Exception as e:
        logger.error("Neo4j graph reload error: %s", e)
        return None
    finally:
        driver.close()


# ─── Health check ─────────────────────────────────────────────────────────────

def neo4j_status() -> dict:
    if not NEO4J_AVAILABLE:
        return {"connected": False, "reason": "driver not installed"}
    driver = _driver()
    if driver is None:
        return {"connected": False, "reason": "credentials not set"}
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            total = result.single()["total"]
        return {"connected": True, "node_count": total}
    except Exception as e:
        return {"connected": False, "reason": str(e)}
    finally:
        driver.close()
