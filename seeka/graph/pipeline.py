"""Graph write pipeline — orchestrates entity resolution + conflict detection.

This module encapsulates the full graph write path so that Memory.dream()
remains clean. The pipeline:
    1. Fetches existing entity catalog from the graph
    2. Resolves incoming entities against existing ones (dedup)
    3. Remaps triple subject/object IDs based on resolution results
    4. Detects temporal conflicts between new and existing triples
    5. Invalidates old edges and writes new entities + edges

Graceful degradation: if the pipeline is not configured (no LLM), the caller
falls back to direct graph writes without resolution/conflict detection.
"""

from __future__ import annotations

import time

from ..models import Entity, Triple
from ..embedding.base import EmbeddingBase
from ..processor.entity_resolver import EntityResolver
from ..processor.graph_conflict import TripleConflictResolver
from .base import GraphBase


class GraphWritePipeline:
    """Orchestrates entity resolution + conflict detection + graph writes.

    Composes EntityResolver and TripleConflictResolver into a single
    ingest() call that handles the full graph write path with quality
    guarantees.

    Args:
        graph: The graph storage backend.
        embedding: Embedding model for entity name similarity.
        model_uri: chak-format model URI for LLM calls.
        api_key: API key for the LLM provider.
        resolution_threshold: Cosine similarity threshold for entity matching.
    """

    def __init__(
        self,
        graph: GraphBase,
        embedding: EmbeddingBase,
        model_uri: str,
        api_key: str,
        resolution_threshold: float = 0.75,
    ):
        self._graph = graph
        self._entity_resolver = EntityResolver(
            embedding, model_uri, api_key, threshold=resolution_threshold
        )
        self._conflict_resolver = TripleConflictResolver(model_uri, api_key)

    def _remap_triples(
        self, triples: list[Triple], id_map: dict[str, str]
    ) -> list[Triple]:
        """Remap triple subject/object IDs using the entity resolution map.

        If an entity was resolved to an existing one, its triples should
        reference the existing entity's ID instead of the new (merged) one.
        """
        remapped: list[Triple] = []
        for tri in triples:
            new_subject = id_map.get(tri.subject_id, tri.subject_id)
            new_object = id_map.get(tri.object_id, tri.object_id)
            if new_subject != tri.subject_id or new_object != tri.object_id:
                # Create a copy with remapped IDs
                remapped.append(Triple(
                    subject_id=new_subject,
                    predicate=tri.predicate,
                    object_id=new_object,
                    description=tri.description,
                    source_memo_id=tri.source_memo_id,
                    valid_from=tri.valid_from,
                    valid_to=tri.valid_to,
                    created_at=tri.created_at,
                ))
            else:
                remapped.append(tri)
        return remapped

    async def _update_aliases(
        self, entities: list[Entity], id_map: dict[str, str]
    ) -> None:
        """Append aliases for merged entities in the graph."""
        for ent in entities:
            resolved_id = id_map.get(ent.id)
            if resolved_id and resolved_id != ent.id:
                # This entity was merged — add its name as alias
                catalog = await self._graph.get_entity_catalog()
                existing = next(
                    (e for e in catalog if e["id"] == resolved_id), None
                )
                if existing:
                    # Build updated aliases string
                    current_aliases = existing.get("aliases", "") or ""
                    parts = [p.strip() for p in current_aliases.split(",") if p.strip()]
                    if ent.name not in parts:
                        parts.append(ent.name)
                    await self._graph.update_entity_aliases(
                        resolved_id, ",".join(parts)
                    )

    async def ingest(
        self, entities: list[Entity], triples: list[Triple]
    ) -> None:
        """Run the full graph write pipeline.

        Steps:
            1. Fetch existing entity catalog
            2. Resolve entities (dedup against existing)
            3. Update aliases for merged entities
            4. Remap triple IDs
            5. Detect temporal conflicts
            6. Apply: invalidate old edges → write new entities → write new edges
        """
        # 1. Fetch existing entity catalog
        catalog = await self._graph.get_entity_catalog()

        # 2. Entity resolution
        new_entities, id_map = await self._entity_resolver.resolve(
            entities, catalog
        )

        # 3. Update aliases for merged entities
        await self._update_aliases(entities, id_map)

        # 4. Remap triple subject/object IDs per resolution
        remapped = self._remap_triples(triples, id_map)

        # 5. Temporal conflict detection
        to_write, invalidations = await self._conflict_resolver.detect(
            remapped, self._graph
        )

        # 6. Apply changes to graph
        now = int(time.time())
        for inv in invalidations:
            await self._graph.invalidate_edges(
                inv["subject_id"], inv["predicate"], inv["object_id"], now
            )

        if new_entities:
            await self._graph.add_entities(new_entities)

        if to_write:
            await self._graph.add_edges(to_write)
