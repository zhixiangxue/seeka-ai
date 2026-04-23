from __future__ import annotations

import asyncio
import os
import warnings

from .archive import Archive
from .notebook import Notebook
from .models import Memo, Note
from .storage.lancedb import LanceDB
from .embedding import create as create_embedding
from .rerank import create as create_reranker
from .processor.agentic import AgenticProcessor
from .processor.conflict import ConflictResolver

_DEFAULT_NAMESPACE = "default"


class Memory:
    """
    Public entry point for seeka.

    Minimal usage (zero config, local embedding):
        mem = Memory("./my_memory")
        await mem.note("User prefers pour-over coffee")
        await mem.dream()
        results = await mem.recall("coffee preference")

    All storage files are placed inside the given directory:
        <path>/           vector store (lancedb)
        <path>/seeka.db   SQLite archive & notebook

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
        self._storage = LanceDB(path, namespace)
        self._embedding = create_embedding(embedding_uri, embedding_api_key)
        if llm_uri and not llm_api_key:
            raise ValueError(
                "llm_api_key is required when llm_uri is set"
            )
        self._processor = (
            AgenticProcessor(model_uri=llm_uri, api_key=llm_api_key, skills=skills)
            if llm_uri
            else None
        )
        self._conflict_resolver = (
            ConflictResolver(model_uri=llm_uri, api_key=llm_api_key)
            if llm_uri
            else None
        )
        self._reranker = create_reranker(rerank_uri, rerank_api_key) if rerank_uri else None
        db_path = os.path.join(path, "seeka.db")
        self._notebook = Notebook(db_path, namespace)
        self._archive = Archive(db_path, namespace)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def note(self, content: str, metadata: dict = None) -> str:
        """Record raw input as a Note. Fast, no network calls. Returns the Note id."""
        n = Note(content=content, metadata=metadata or {}, namespace=self._namespace)
        n = await self._notebook.add(n)
        return n.id

    async def dream(self) -> list[Memo]:
        """Process all pending Notes. Runs processor + embedding + storage writes."""
        notes = await self._notebook.pendings()
        if not notes:
            return []

        combined = "\n".join(note.content for note in notes)

        try:
            if self._processor:
                raw_memos = await self._processor.process(combined)
            else:
                raw_memos = [Memo(content=note.content, metadata=note.metadata) for note in notes]

            for memo in raw_memos:
                memo.namespace = self._namespace

            # 批量 embed 所有新 Memo，结果直接写入 memo.embedding
            embeddings = await self._embedding.embed_batch([m.content for m in raw_memos])
            for memo, emb in zip(raw_memos, embeddings):
                memo.embedding = emb

            # 并发搜索候选旧 Memo，收集唯一候选集合做一次批量冲突检测
            all_memos: list[Memo] = []
            if self._conflict_resolver:
                search_results = await asyncio.gather(
                    *[self._storage.search(m.embedding, n=5) for m in raw_memos]
                )
                # 收集所有候选，去重
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
                # 一次 LLM 调用解决所有冲突
                conflict_map = await self._conflict_resolver.resolve_batch(
                    raw_memos, all_candidates
                )
                ids_to_delete: set[str] = set()
                for del_ids in conflict_map.values():
                    ids_to_delete.update(del_ids)
                for del_id in ids_to_delete:
                    await self._storage.delete(del_id)
                    await self._archive.delete(del_id)

            # 批量写入全部新 Memo
            await self._storage.add_batch(raw_memos)
            await self._archive.save_batch(raw_memos)
            all_memos = list(raw_memos)

            for note in notes:
                await self._notebook.done(note)

            return all_memos

        except Exception:
            for note in notes:
                await self._notebook.fail(note)
            raise

    async def recall(self, query: str, n: int = 5, filter: dict | None = None) -> list[Memo]:
        """
        Semantic search over consolidated memories.
        filter: optional MongoDB-style metadata filter, e.g.
            {"user_id": {"$eq": "u123"}}
            {"$and": [{"source": {"$eq": "chat"}}, {"score": {"$gte": 0.8}}]}
        """
        if await self._notebook.pendings():
            warnings.warn(
                "Unprocessed notes exist. Call dream() before recall() to include them.",
                stacklevel=2,
            )

        embedding = await self._embedding.embed(query)
        results = await self._storage.search(
            embedding,
            n if not self._reranker else n * 3,
            filter=filter,
        )

        if self._reranker and results:
            docs = [r.get("content", "") for r in results]
            ranked_indices = await self._reranker.rerank(query, docs)
            results = [results[i] for i in ranked_indices[:n]]

        return [
            Memo(
                id=r.get("id", ""),
                content=r.get("content", ""),
                metadata=r.get("metadata", {}),
                namespace=self._namespace,
            )
            for r in results
        ]

    async def delete(self, id: str) -> None:
        """Delete a Memo by id from both VectorDB and the archive."""
        await self._storage.delete(id)
        await self._archive.delete(id)

    async def get(self, id: str) -> Memo | None:
        """Return a single Memo by id, or None if not found."""
        return await self._archive.get(id)

    async def update(self, id: str, content: str, metadata: dict = None) -> Memo:
        """
        Update an existing Memo's content (and optionally metadata).
        Re-embeds the new content and writes both SeekDB and archive.
        Raises KeyError if the Memo does not exist.
        """
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
        await self._storage.update(updated)
        await self._archive.update(updated.id, updated.content, updated.metadata)
        return await self._archive.get(updated.id)

    async def memos(self, limit: int = 100, offset: int = 0) -> list[Memo]:
        """Return all Memos for the current namespace (newest first)."""
        return await self._archive.memos(limit=limit, offset=offset)

    async def forget(self) -> None:
        """Wipe all Memos and pending Notes for the current namespace."""
        await self._storage.forget()
        await self._archive.forget()
        await self._notebook.forget()

    async def remember(self, content: str, metadata: dict = None) -> list[Memo]:
        """Single-step convenience: note() + dream() in one call."""
        await self.note(content, metadata)
        return await self.dream()