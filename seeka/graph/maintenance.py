"""Graph maintenance — offline operations for graph health.

These operations are NOT on the hot path of dream/recall. They run
periodically or on-demand via Memory.maintain() to keep the graph clean.

Operations:
    - Entity merge: combine two nodes into one, transferring edges
    - Orphan cleanup: remove zero-degree nodes
    - Predicate stats: usage counts for detecting synonym bloat
"""

from __future__ import annotations

from .base import GraphBase


class GraphMaintenance:
    """Offline maintenance operations for keeping the graph healthy.

    Args:
        graph: The graph storage backend.
    """

    def __init__(self, graph: GraphBase):
        self._graph = graph

    async def merge_entities(self, keep_id: str, remove_id: str) -> dict:
        """Merge remove_id into keep_id.

        Transfers all edges from remove_id to keep_id, updates aliases on
        keep_id with remove_id's name, then deletes remove_id.

        Returns stats: {outgoing_transferred, incoming_transferred}.
        """
        stats = {"outgoing_transferred": 0, "incoming_transferred": 0}

        # Get remove_id's name for alias
        catalog = await self._graph.get_entity_catalog()
        remove_ent = next((e for e in catalog if e["id"] == remove_id), None)
        keep_ent = next((e for e in catalog if e["id"] == keep_id), None)

        if not remove_ent or not keep_ent:
            return stats

        # Transfer outgoing edges: (remove_id)-[r]->(target) → (keep_id)-[r]->(target)
        outgoing = await self._graph.query(
            f"MATCH (src:Entity {{id:'{remove_id}'}})-[r:RELATES]->(dst:Entity) "
            f"RETURN dst.id AS dst_id, r.predicate AS pred, r.description AS detail, "
            f"r.source_memo_id AS memo, r.valid_from AS vf, r.valid_to AS vt, "
            f"r.created_at AS cat;"
        )
        for row in outgoing:
            if row["dst_id"] == keep_id:
                continue  # avoid self-loops
            from ..models import Triple
            edge = Triple(
                subject_id=keep_id,
                predicate=row["pred"],
                object_id=row["dst_id"],
                description=row["detail"] or "",
                source_memo_id=row["memo"] or "",
                valid_from=row["vf"],
                valid_to=row["vt"],
                created_at=row["cat"],
            )
            await self._graph.add_edges([edge])
            stats["outgoing_transferred"] += 1

        # Transfer incoming edges: (source)-[r]->(remove_id) → (source)-[r]->(keep_id)
        incoming = await self._graph.query(
            f"MATCH (src:Entity)-[r:RELATES]->(dst:Entity {{id:'{remove_id}'}}) "
            f"RETURN src.id AS src_id, r.predicate AS pred, r.description AS detail, "
            f"r.source_memo_id AS memo, r.valid_from AS vf, r.valid_to AS vt, "
            f"r.created_at AS cat;"
        )
        for row in incoming:
            if row["src_id"] == keep_id:
                continue
            from ..models import Triple
            edge = Triple(
                subject_id=row["src_id"],
                predicate=row["pred"],
                object_id=keep_id,
                description=row["detail"] or "",
                source_memo_id=row["memo"] or "",
                valid_from=row["vf"],
                valid_to=row["vt"],
                created_at=row["cat"],
            )
            await self._graph.add_edges([edge])
            stats["incoming_transferred"] += 1

        # Update keep_id's aliases with remove_id's name
        current_aliases = keep_ent.get("aliases", "") or ""
        parts = [p.strip() for p in current_aliases.split(",") if p.strip()]
        if remove_ent["name"] and remove_ent["name"] not in parts:
            parts.append(remove_ent["name"])
        await self._graph.update_entity_aliases(keep_id, ",".join(parts))

        # Delete remove_id (edges + node)
        await self._graph.delete_entities([remove_id])

        return stats

    async def cleanup_orphans(self) -> int:
        """Remove entities with zero edges (no incoming or outgoing).

        Returns the count of deleted orphan nodes.
        """
        # Find orphans using NOT EXISTS subqueries
        orphans = await self._graph.query(
            "MATCH (n:Entity) "
            "WHERE NOT EXISTS { MATCH (n)-[:RELATES]->() } "
            "AND NOT EXISTS { MATCH ()-[:RELATES]->(n) } "
            "RETURN n.id AS eid;"
        )

        if not orphans:
            return 0

        orphan_ids = [row["eid"] for row in orphans]
        await self._graph.delete_entities(orphan_ids)
        return len(orphan_ids)

    async def predicate_stats(self) -> list[dict]:
        """Return predicate usage counts, sorted by frequency descending.

        Useful for detecting synonym bloat (multiple predicates meaning
        the same thing) and understanding graph structure.

        Returns: [{predicate: str, count: int}]
        """
        rows = await self._graph.query(
            "MATCH ()-[r:RELATES]->() "
            "RETURN r.predicate AS pred;"
        )

        # Count manually (avoid DISTINCT/GROUP BY which may crash NeuG+LanceDB)
        counts: dict[str, int] = {}
        for row in rows:
            p = row["pred"]
            counts[p] = counts.get(p, 0) + 1

        result = [
            {"predicate": p, "count": c}
            for p, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)
        ]
        return result
