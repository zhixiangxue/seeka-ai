import os
import warnings

from .archive import Archive
from .notebook import Notebook
from .models import Memo, Note
from .storage.seekdb import SeekDB
from .embedding import create as create_embedding
from .rerank import create as create_reranker
from .processor.agentic import AgenticProcessor

_DEFAULT_NAMESPACE = "default"


class Memory:
    """
    Public entry point for seeka.

    Minimal usage (zero config, local embedding):
        mem = Memory("./my.db")
        await mem.note("User prefers pour-over coffee")
        await mem.dream()
        results = await mem.recall("coffee preference")

    Full configuration (chak URI format for model_uri):
        mem = Memory(
            "./my.db",
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
    ):
        self._namespace = namespace
        self._storage = SeekDB(path)
        self._embedding = create_embedding(embedding_uri, embedding_api_key)
        if llm_uri and not llm_api_key:
            raise ValueError(
                "llm_api_key is required when llm_uri is set"
            )
        self._processor = (
            AgenticProcessor(model_uri=llm_uri, api_key=llm_api_key)
            if llm_uri
            else None
        )
        self._reranker = create_reranker(rerank_uri, rerank_api_key) if rerank_uri else None
        db_path = self._derive_db_path(path)
        self._notebook = Notebook(db_path)
        self._archive = Archive(db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _derive_db_path(path: str) -> str:
        base, _ = os.path.splitext(path)
        return base + "_sqlite.db"

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
        notes = await self._notebook.pendings(self._namespace)
        if not notes:
            return []

        combined = "\n".join(note.content for note in notes)

        try:
            if self._processor:
                raw_memos = await self._processor.process(combined)
            else:
                raw_memos = [Memo(content=note.content) for note in notes]

            all_memos: list[Memo] = []
            for memo in raw_memos:
                memo.namespace = self._namespace
                embedding = await self._embedding.embed(memo.content)
                await self._storage.add(memo, embedding)
                await self._archive.save(memo)
                all_memos.append(memo)

            for note in notes:
                await self._notebook.done(note)

            return all_memos

        except Exception:
            for note in notes:
                await self._notebook.fail(note)
            raise

    async def recall(self, query: str, n: int = 5) -> list[Memo]:
        """Semantic search over consolidated memories."""
        if await self._notebook.pendings(self._namespace):
            warnings.warn(
                "Unprocessed notes exist. Call dream() before recall() to include them.",
                stacklevel=2,
            )

        embedding = await self._embedding.embed(query)
        results = await self._storage.search(
            embedding,
            self._namespace,
            n if not self._reranker else n * 3,
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
        """Delete a Memo by id from both SeekDB and the archive."""
        memo = Memo(id=id, content="")
        await self._storage.delete(id, self._namespace)
        await self._archive.delete(memo)
