"""NeuG (Kùzu-derived) graph storage backend.

NeuG is an embedded graph database from Alibaba with Cypher dialect support.
This implementation uses the universal schema pattern: one Entity node table
and one RELATES relationship table, storing type/predicate as string properties.

Known NeuG v0.1 limitations handled here:
- Only scalar property types (no arrays, BLOB, UUID)
- No parameterized queries — values are escaped inline
- Reserved words (desc, from, to) must not be used as aliases
- column_names() is a method, not an attribute
- No startNode()/endNode() functions
"""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Entity, Triple
from .base import GraphBase


def _q(s: str) -> str:
    """Escape a string for inline Cypher literal (single-quoted)."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


class NeuGGraph(GraphBase):
    """NeuG-backed graph storage using the universal schema pattern."""

    _SCHEMA = [
        """CREATE NODE TABLE IF NOT EXISTS Entity(
            id STRING, name STRING, type STRING, description STRING,
            aliases STRING, namespace STRING, created_at INT64,
            PRIMARY KEY(id));""",
        """CREATE REL TABLE IF NOT EXISTS RELATES(
            FROM Entity TO Entity,
            predicate STRING, description STRING, source_memo_id STRING,
            valid_from INT64, valid_to INT64, created_at INT64);""",
    ]

    def __init__(self, path: str, namespace: str):
        self._path = Path(path) / "graph_neug"
        self._namespace = namespace
        self._db = None
        self._conn = None  # single persistent connection
        self._init_db()

    def _init_db(self) -> None:
        """Create the database directory, schema tables, and persistent connection."""
        self._path.mkdir(parents=True, exist_ok=True)

        # Redirect NeuG glog output into the graph DB directory instead of CWD
        log_dir = str(self._path / "logs")
        os.makedirs(log_dir, exist_ok=True)
        os.environ.setdefault("GLOG_log_dir", log_dir)

        import neug

        self._db = neug.Database(str(self._path))
        self._conn = self._db.connect()
        for stmt in self._SCHEMA:
            self._conn.execute(stmt)

    def _get_conn(self):
        """Return the persistent connection (NeuG crashes with repeated connect/close cycles)."""
        return self._conn

    # ------------------------------------------------------------------
    # Sync implementations (NeuG has no async API)
    # ------------------------------------------------------------------

    def _add_entities_sync(self, entities: list[Entity]) -> None:
        conn = self._get_conn()
        for ent in entities:
            conn.execute(
                f"CREATE (:Entity {{"
                f"id:{_q(ent.id)}, name:{_q(ent.name)}, "
                f"type:{_q(ent.type)}, description:{_q(ent.description)}, "
                f"aliases:{_q(ent.aliases)}, namespace:{_q(self._namespace)}, "
                f"created_at:{ent.created_at}}});"
            )

    def _add_edges_sync(self, edges: list[Triple]) -> None:
        conn = self._get_conn()
        for edge in edges:
            conn.execute(
                f"MATCH (a:Entity {{id:{_q(edge.subject_id)}}}), "
                f"      (b:Entity {{id:{_q(edge.object_id)}}}) "
                f"CREATE (a)-[:RELATES {{"
                f"predicate:{_q(edge.predicate)}, "
                f"description:{_q(edge.description)}, "
                f"source_memo_id:{_q(edge.source_memo_id)}, "
                f"valid_from:{edge.valid_from}, "
                f"valid_to:{edge.valid_to}, "
                f"created_at:{edge.created_at}}}]->(b);"
            )

    def _query_sync(self, statement: str) -> list[dict]:
        conn = self._get_conn()
        result = conn.execute(statement)
        columns = result.column_names()
        rows = []
        for row in result:
            rows.append(dict(zip(columns, row)))
        return rows

    def _get_entity_catalog_sync(self) -> list[dict]:
        conn = self._get_conn()
        result = conn.execute(
            f"MATCH (n:Entity) WHERE n.namespace = {_q(self._namespace)} "
            f"RETURN n.id AS eid, n.name AS ename, "
            f"n.type AS etype, n.description AS edesc;"
        )
        columns = result.column_names()
        rows = []
        for row in result:
            d = dict(zip(columns, row))
            rows.append({
                "id": d["eid"],
                "name": d["ename"],
                "type": d["etype"],
                "description": d["edesc"],
            })
        return rows

    def _get_predicate_catalog_sync(self) -> list[str]:
        conn = self._get_conn()
        # NOTE: DISTINCT on relationship queries crashes NeuG when LanceDB
        # is loaded in the same process (SIGSEGV). Workaround: fetch all
        # predicates and deduplicate in Python.
        result = conn.execute(
            f"MATCH (a:Entity)-[r:RELATES]->(b:Entity) "
            f"WHERE a.namespace = {_q(self._namespace)} "
            f"RETURN r.predicate AS pred;"
        )
        seen = set()
        preds = []
        for row in result:
            p = row[0]
            if p not in seen:
                seen.add(p)
                preds.append(p)
        return preds

    def _invalidate_edges_sync(
        self, subject_id: str, predicate: str, object_id: str, timestamp: int
    ) -> int:
        conn = self._get_conn()
        # Count matching active edges first (NeuG has no RETURN on SET)
        result = conn.execute(
            f"MATCH (s:Entity {{id:{_q(subject_id)}}})"
            f"-[r:RELATES {{predicate:{_q(predicate)}}}]->"
            f"(o:Entity {{id:{_q(object_id)}}}) "
            f"WHERE r.valid_to = 0 "
            f"RETURN count(r) AS cnt;"
        )
        count = 0
        for row in result:
            count = row[0]
        if count > 0:
            conn.execute(
                f"MATCH (s:Entity {{id:{_q(subject_id)}}})"
                f"-[r:RELATES {{predicate:{_q(predicate)}}}]->"
                f"(o:Entity {{id:{_q(object_id)}}}) "
                f"WHERE r.valid_to = 0 "
                f"SET r.valid_to = {timestamp};"
            )
        return count

    def _find_active_edges_sync(
        self, subject_id: str, object_id: str, predicates: list[str] | None = None
    ) -> list[dict]:
        conn = self._get_conn()
        if predicates:
            pred_list = ", ".join(_q(p) for p in predicates)
            result = conn.execute(
                f"MATCH (s:Entity {{id:{_q(subject_id)}}})"
                f"-[r:RELATES]->"
                f"(o:Entity {{id:{_q(object_id)}}}) "
                f"WHERE r.valid_to = 0 AND r.predicate IN [{pred_list}] "
                f"RETURN r.predicate AS pred, r.description AS detail, "
                f"r.valid_from AS vf, r.source_memo_id AS memo;"
            )
        else:
            result = conn.execute(
                f"MATCH (s:Entity {{id:{_q(subject_id)}}})"
                f"-[r:RELATES]->"
                f"(o:Entity {{id:{_q(object_id)}}}) "
                f"WHERE r.valid_to = 0 "
                f"RETURN r.predicate AS pred, r.description AS detail, "
                f"r.valid_from AS vf, r.source_memo_id AS memo;"
            )
        rows = []
        for row in result:
            rows.append({
                "predicate": row[0],
                "description": row[1],
                "valid_from": row[2],
                "source_memo_id": row[3],
            })
        return rows

    def _delete_entities_sync(self, entity_ids: list[str]) -> None:
        conn = self._get_conn()
        for eid in entity_ids:
            # Remove all edges touching the entity first
            conn.execute(
                f"MATCH (n:Entity {{id:{_q(eid)}}})-[r:RELATES]->() DELETE r;"
            )
            conn.execute(
                f"MATCH ()-[r:RELATES]->(n:Entity {{id:{_q(eid)}}}) DELETE r;"
            )
            conn.execute(
                f"MATCH (n:Entity {{id:{_q(eid)}}}) DELETE n;"
            )

    def _update_entity_aliases_sync(self, entity_id: str, aliases: str) -> None:
        conn = self._get_conn()
        conn.execute(
            f"MATCH (e:Entity {{id:{_q(entity_id)}}}) "
            f"SET e.aliases = {_q(aliases)};"
        )

    def _forget_sync(self) -> None:
        conn = self._get_conn()
        # Delete edges first (NeuG requires edges removed before nodes)
        conn.execute(
            f"MATCH (a:Entity {{namespace:{_q(self._namespace)}}})"
            f"-[r:RELATES]->(b:Entity) DELETE r;"
        )
        # Also delete incoming edges from other namespaces
        conn.execute(
            f"MATCH (a:Entity)-[r:RELATES]->"
            f"(b:Entity {{namespace:{_q(self._namespace)}}}) DELETE r;"
        )
        # Delete nodes
        conn.execute(
            f"MATCH (n:Entity {{namespace:{_q(self._namespace)}}}) DELETE n;"
        )

    # ------------------------------------------------------------------
    # Async interface (sync under the hood — NeuG is not thread-safe)
    # ------------------------------------------------------------------

    async def add_entities(self, entities: list[Entity]) -> None:
        if not entities:
            return
        self._add_entities_sync(entities)

    async def add_edges(self, edges: list[Triple]) -> None:
        if not edges:
            return
        self._add_edges_sync(edges)

    async def query(self, statement: str) -> list[dict]:
        return self._query_sync(statement)

    async def get_entity_catalog(self) -> list[dict]:
        return self._get_entity_catalog_sync()

    async def get_predicate_catalog(self) -> list[str]:
        return self._get_predicate_catalog_sync()

    async def forget(self) -> None:
        self._forget_sync()

    async def invalidate_edges(
        self, subject_id: str, predicate: str, object_id: str, timestamp: int
    ) -> int:
        return self._invalidate_edges_sync(subject_id, predicate, object_id, timestamp)

    async def find_active_edges(
        self, subject_id: str, object_id: str, predicates: list[str] | None = None
    ) -> list[dict]:
        return self._find_active_edges_sync(subject_id, object_id, predicates)

    async def delete_entities(self, entity_ids: list[str]) -> None:
        if not entity_ids:
            return
        self._delete_entities_sync(entity_ids)

    async def update_entity_aliases(self, entity_id: str, aliases: str) -> None:
        self._update_entity_aliases_sync(entity_id, aliases)
