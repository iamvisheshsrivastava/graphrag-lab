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
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Lazy import — only fails at connection time, not import time
try:
    from neo4j import GraphDatabase, exceptions as neo4j_exc
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logger.warning("neo4j driver not installed — graph persistence disabled")


def _driver():
    uri  = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD")
    if not uri or not pwd:
        return None
    return GraphDatabase.driver(uri, auth=(user, pwd))


# ─── Write ────────────────────────────────────────────────────────────────────

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
            # Clear previous graph
            session.run("MATCH (n) DETACH DELETE n")

            # Write nodes
            for node in graph_data.get("nodes", []):
                if node["type"] == "requirement":
                    session.run(
                        """
                        MERGE (r:Requirement {id: $id})
                        SET r.label     = $label,
                            r.text      = $text,
                            r.req_type  = $req_type,
                            r.sae_level = $sae_level,
                            r.domain    = $domain
                        """,
                        id=node["id"],
                        label=node.get("label", node["id"]),
                        text=node.get("properties", {}).get("text", ""),
                        req_type=node.get("properties", {}).get("req_type", ""),
                        sae_level=node.get("properties", {}).get("sae_level", ""),
                        domain=node.get("properties", {}).get("domain", ""),
                    )
                else:
                    session.run(
                        """
                        MERGE (e:Entity {id: $id})
                        SET e.label       = $label,
                            e.entity_type = $entity_type
                        """,
                        id=node["id"],
                        label=node.get("label", node["id"]),
                        entity_type=node["type"],
                    )

            # Write edges
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
            for edge in graph_data.get("edges", []):
                rel = REL_MAP.get(edge["relation"], "RELATED_TO")
                cypher = f"""
                    MATCH (a {{id: $src}}), (b {{id: $tgt}})
                    MERGE (a)-[:{rel}]->(b)
                """
                session.run(cypher, src=edge["source"], tgt=edge["target"])

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
    Execute an arbitrary read-only Cypher query.
    Returns { columns, rows, row_count } or { error }.
    """
    if not NEO4J_AVAILABLE:
        return {"error": "neo4j driver not installed"}
    driver = _driver()
    if driver is None:
        return {"error": "NEO4J_URI / NEO4J_PASSWORD not configured"}

    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run(query, **(params or {}))
            records = result.data()
            columns = list(records[0].keys()) if records else []
            # Serialize neo4j Node/Relationship objects to plain dicts
            rows = [_serialize_record(r) for r in records]
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error": str(e)}
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
