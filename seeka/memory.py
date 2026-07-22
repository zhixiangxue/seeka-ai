from __future__ import annotations

import asyncio
import os
import sys
import warnings
from enum import Enum

from .archive import Archive
from .notebook import Notebook
from .models import Memo, Note
from .embedding import create as create_embedding
from .rerank import create as create_reranker
from .processor.agentic import AgenticProcessor
from .processor.conflict import ConflictResolver

_DEFAULT_NAMESPACE = "default"


class VectorDB(str, Enum):
    """Supported vector database backends.

    Usage:
        from seeka import Memory, VectorDB
        mem = Memory("./data", vector_db=VectorDB.ZVEC)
    """
    LANCEDB = "lancedb"
    SEEKDB = "seekdb"
    ZVEC = "zvec"

    @property
    def cls(self):
        """Return the StorageBase implementation class for this backend."""
        from .storage import LanceDB, SeekDB, ZvecDB
        return {
            VectorDB.LANCEDB: LanceDB,
            VectorDB.SEEKDB: SeekDB,
            VectorDB.ZVEC: ZvecDB,
        }[self]


class GraphDB(str, Enum):
    """Supported graph database backends."""
    NEUG = "neug"


def _make_graph(graph_db: GraphDB, path: str, namespace: str, llm_uri: str | None, llm_api_key: str | None):
    """Factory: instantiate graph backend + matching statement generator."""
    if graph_db == GraphDB.NEUG:
        from .graph import NeuGGraph
        from .statement import CypherGenerator, NEUG_DIALECT_NOTES
        graph = NeuGGraph(path, namespace)
        gen = (
            CypherGenerator(
                model_uri=llm_uri,
                api_key=llm_api_key,
                dialect_notes=NEUG_DIALECT_NOTES,
            )
            if llm_uri
            else None
        )
        return graph, gen
    raise ValueError(f"Unknown graph_db: {graph_db!r}. Available: {[g.value for g in GraphDB]}")


class Memory:
    """
    Public entry point for seeka.

    Minimal usage (zero config, local embedding):
        mem = Memory("./my_memory")
        await mem.note("User prefers pour-over coffee")
        await mem.dream()
        results = await mem.recall("coffee preference")

    All storage files are placed inside the given directory:
        <path>/           vector store (lancedb / seekdb / zvec)
        <path>/seeka.db   SQLite archive & notebook

    Choose a vector backend via the VectorDB enum:
        from seeka import Memory, VectorDB

        mem = Memory("./my_memory", vector_db=VectorDB.ZVEC)
        mem = Memory("./my_memory", vector_db=VectorDB.SEEKDB)
        mem = Memory("./my_memory", vector_db=VectorDB.LANCEDB)   # default

    Full configuration (chak URI format for model_uri):
        mem = Memory(
            "./my_memory",
            embedding_uri="openai/text-embedding-3-small",
            embedding_api_key="sk-...",
            llm_uri="openai/gpt-4o-mini",
            llm_api_key="sk-...",
        )
    """

    def __init__(
        self,
        path: str,
        namespace: str = _DEFAULT_NAMESPACE,
        vector_db: VectorDB = VectorDB.LANCEDB,
        graph_db: GraphDB | None = None,
        embedding_uri: str = None,
        embedding_api_key: str = None,
        llm_uri: str = None,
        llm_api_key: str = None,
        rerank_uri: str = None,
        rerank_api_key: str = None,
        skills: list[str] | None = None,
    ):
        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        self._namespace = namespace

        try:
            self._vector = vector_db.cls(path, namespace)
        except ImportError as e:
            # LanceDB is always available (core dependency).
            # For zvec / seekdb the enum value doubles as the pip extra name.
            hint = ""
            if vector_db is not VectorDB.LANCEDB:
                hint = f"\nInstall it with: pip install 'seeka[{vector_db.value}]'"
            raise RuntimeError(
                f"Vector DB '{vector_db.value}' is not available — "
                f"the required package is not installed or not supported "
                f"on this platform ({sys.platform}).{hint}\n"
                f"Error: {e}"
            ) from e

        # Graph layer (opt-in)
        self._graph = None
        self._statement_gen = None
        self._graph_pipeline = None
        self._maintenance = None
        if graph_db is not None:
            self._graph, self._statement_gen = _make_graph(
                graph_db, path, namespace, llm_uri, llm_api_key
            )

        self._embedding = create_embedding(embedding_uri, embedding_api_key)
        if llm_uri and not llm_api_key:
            raise ValueError(
                "llm_api_key is required when llm_uri is set"
            )
        self._processor = (
            AgenticProcessor(
                model_uri=llm_uri, api_key=llm_api_key,
                skills=skills, graph_enabled=(self._graph is not None),
            )
            if llm_uri
            else None
        )
        self._conflict_resolver = (
            ConflictResolver(model_uri=llm_uri, api_key=llm_api_key)
            if llm_uri
            else None
        )
        self._reranker = create_reranker(rerank_uri, rerank_api_key) if rerank_uri else None

        # Graph write pipeline (entity resolution + temporal conflict detection)
        if self._graph and llm_uri:
            from .graph.pipeline import GraphWritePipeline
            from .graph.maintenance import GraphMaintenance
            self._graph_pipeline = GraphWritePipeline(
                self._graph, self._embedding, llm_uri, llm_api_key
            )
            self._maintenance = GraphMaintenance(self._graph)

        db_path = os.path.join(path, "seeka.db")
        self._notebook = Notebook(db_path, namespace)
        self._archive = Archive(db_path, namespace)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def note(self, content: str, key: str | None = None, metadata: dict = None) -> str:
        """Record raw input as a Note. Fast, no network calls. Returns the Note id.

        When `key` is provided, behaves as upsert: if a Note with the same key
        already exists in this namespace, its content/metadata are overwritten.
        This enables LLM-addressable working memory (like a scratchpad).
        """
        n = Note(content=content, key=key, metadata=metadata or {}, namespace=self._namespace)
        if key:
            n = await self._notebook.upsert_by_key(n)
        else:
            n = await self._notebook.add(n)
        return n.id

    async def dream(self) -> list[Memo]:
        """Process all pending Notes. Runs processor + embedding + storage writes.

        When graph_db is configured, also extracts entities and triples
        into the knowledge graph (dual pipeline).
        """
        notes = await self._notebook.pendings()
        if not notes:
            return []

        combined = "\n".join(note.content for note in notes)

        try:
            if self._processor:
                raw_memos, entities, triples = await self._processor.process(combined)
            else:
                raw_memos = [Memo(content=note.content, metadata=note.metadata) for note in notes]
                entities, triples = [], []

            for memo in raw_memos:
                memo.namespace = self._namespace

            # Batch embed all new Memos
            embeddings = await self._embedding.embed_batch([m.content for m in raw_memos])
            for memo, emb in zip(raw_memos, embeddings):
                memo.embedding = emb

            # Conflict detection against existing memos
            all_memos: list[Memo] = []
            if self._conflict_resolver:
                search_results = await asyncio.gather(
                    *[self._vector.search(m.embedding, n=5) for m in raw_memos]
                )
                seen_ids: set[str] = set()
                all_candidates: list[Memo] = []
                for hits in search_results:
                    for r in hits:
                        if r["id"] not in seen_ids:
                            seen_ids.add(r["id"])
                            all_candidates.append(Memo(
                                id=r["id"],
                                content=r["content"],
                                metadata=r.get("metadata", {}),
                                namespace=self._namespace,
                            ))
                conflict_map = await self._conflict_resolver.resolve_batch(
                    raw_memos, all_candidates
                )
                ids_to_delete: set[str] = set()
                for del_ids in conflict_map.values():
                    ids_to_delete.update(del_ids)
                for del_id in ids_to_delete:
                    await self._vector.delete(del_id)
                    await self._archive.delete(del_id)

            # Write memos to vector store + archive
            await self._vector.add_batch(raw_memos)
            await self._archive.save_batch(raw_memos)
            all_memos = list(raw_memos)

            # Write entities + triples to graph (if graph layer is active)
            if self._graph and (entities or triples):
                for ent in entities:
                    ent.namespace = self._namespace
                # Link triples to their source memo batch
                batch_ref = raw_memos[0].id if raw_memos else ""
                for tri in triples:
                    if not tri.source_memo_id:
                        tri.source_memo_id = batch_ref

                if self._graph_pipeline:
                    # Full pipeline: entity resolution + conflict detection
                    await self._graph_pipeline.ingest(entities, triples)
                else:
                    # Fallback: direct write without resolution/conflict
                    await self._graph.add_entities(entities)
                    await self._graph.add_edges(triples)

            for note in notes:
                await self._notebook.done(note)

            return all_memos

        except Exception:
            for note in notes:
                await self._notebook.fail(note)
            raise

    async def recall(self, query: str, n: int = 5, filter: dict | None = None) -> list[Memo]:
        """
        Multi-path retrieval over consolidated memories.

        Path 1 (vector): Semantic similarity search over memo embeddings.
        Path 2 (graph): text2statement → execute → format as Memo-like results.

        Graph results are best-effort and appended after vector results.
        filter: optional MongoDB-style metadata filter for vector search.
        """
        if await self._notebook.pendings():
            warnings.warn(
                "Unprocessed notes exist. Call dream() before recall() to include them.",
                stacklevel=2,
            )

        # -- Path 1: Vector search --
        embedding = await self._embedding.embed(query)
        results = await self._vector.search(
            embedding,
            n if not self._reranker else n * 3,
            filter=filter,
        )

        if self._reranker and results:
            docs = [r.get("content", "") for r in results]
            ranked_indices = await self._reranker.rerank(query, docs)
            results = [results[i] for i in ranked_indices[:n]]

        vector_memos = [
            Memo(
                id=r.get("id", ""),
                content=r.get("content", ""),
                metadata=r.get("metadata", {}),
                namespace=self._namespace,
            )
            for r in results
        ]

        # -- Path 2: Graph recall (best-effort) --
        graph_memos: list[Memo] = []
        if self._graph and self._statement_gen:
            try:
                catalog = await self._graph.get_entity_catalog()
                predicates = await self._graph.get_predicate_catalog()
                if catalog:
                    cypher = await self._statement_gen.generate(query, catalog, predicates)
                    rows = await self._graph.query(cypher)
                    for row in rows:
                        content = " | ".join(f"{k}: {v}" for k, v in row.items())
                        graph_memos.append(Memo(
                            content=content,
                            metadata={"source": "graph"},
                            namespace=self._namespace,
                        ))
            except Exception:
                pass  # graph recall never blocks vector results

        # -- Merge: vector first, then unique graph results --
        seen_contents = {m.content for m in vector_memos}
        for gm in graph_memos:
            if gm.content not in seen_contents:
                vector_memos.append(gm)

        return vector_memos

    async def delete(self, id: str) -> None:
        """Delete a Memo by id from both VectorDB and the archive."""
        await self._vector.delete(id)
        await self._archive.delete(id)

    async def get(self, id: str) -> Memo | None:
        """Return a single Memo by id, or None if not found."""
        return await self._archive.get(id)

    async def update(self, id: str, content: str, metadata: dict = None) -> Memo:
        """Update an existing Memo's content (and optionally metadata).
        Re-embeds the new content and writes both vector store and archive.
        Raises KeyError if the Memo does not exist."""
        existing = await self._archive.get(id)
        if existing is None:
            raise KeyError(f"Memo {id!r} not found")

        new_metadata = metadata if metadata is not None else existing.metadata
        updated = Memo(
            id=existing.id,
            content=content,
            metadata=new_metadata,
            namespace=existing.namespace,
            created=existing.created,
        )
        updated.embedding = await self._embedding.embed(content)
        await self._vector.update(updated)
        await self._archive.update(updated.id, updated.content, updated.metadata)
        return await self._archive.get(updated.id)

    async def memos(self, limit: int = 100, offset: int = 0) -> list[Memo]:
        """Return all Memos for the current namespace (newest first)."""
        return await self._archive.memos(limit=limit, offset=offset)

    async def forget(self) -> None:
        """Wipe all Memos, pending Notes, and graph data for the current namespace."""
        await self._vector.forget()
        await self._archive.forget()
        await self._notebook.forget()
        if self._graph:
            await self._graph.forget()

    async def maintain(self) -> dict:
        """Run offline graph maintenance operations.

        Performs orphan cleanup (removes zero-degree nodes) and returns
        predicate usage statistics for synonym detection.

        Returns a dict with:
            - orphans_removed: int — count of deleted orphan nodes
            - predicates: list[{predicate, count}] — usage stats
        """
        if not self._maintenance:
            return {"orphans_removed": 0, "predicates": []}
        orphans = await self._maintenance.cleanup_orphans()
        stats = await self._maintenance.predicate_stats()
        return {"orphans_removed": orphans, "predicates": stats}

    async def merge_entities(self, keep_id: str, remove_id: str) -> dict:
        """Merge two graph entities into one.

        Transfers all edges from remove_id to keep_id, updates aliases,
        then deletes remove_id. Useful when duplicate entities are discovered.

        Returns stats: {outgoing_transferred, incoming_transferred}.
        """
        if not self._maintenance:
            raise RuntimeError(
                "Graph maintenance requires graph_db to be configured"
            )
        return await self._maintenance.merge_entities(keep_id, remove_id)

    async def remember(self, content: str, metadata: dict = None) -> list[Memo]:
        """Single-step convenience: note() + dream() in one call."""
        await self.note(content, metadata=metadata)
        return await self.dream()

    # ------------------------------------------------------------------
    # Key-based Note access (LLM working memory)
    # ------------------------------------------------------------------

    async def get_note(self, key: str) -> Note | None:
        """Retrieve a Note by its semantic key. Returns None if not found."""
        return await self._notebook.get_by_key(key)

    async def list_notes(self) -> list[dict]:
        """List all keyed Notes as [{key, preview}] for the current namespace."""
        pairs = await self._notebook.list_keys()
        return [{"key": k, "preview": v} for k, v in pairs]

    async def delete_note(self, key: str) -> bool:
        """Delete a Note by key. Returns True if deleted, False if not found."""
        return await self._notebook.delete_by_key(key)