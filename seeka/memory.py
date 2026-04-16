import uuid

from .models import Memo
from .storage.seekdb import SeekDB
from .embedding.base import EmbeddingBase
from .embedding.local import LocalEmbedding
from .embedding.openai import OpenAIEmbedding
from .rerank.base import RerankBase
from .processor.base import ProcessorBase
from .processor.agent import AgentProcessor

_DEFAULT_NAMESPACE = "default"


class Memory:
    """
    Public entry point for seeka. Assembles all components and exposes add / search / delete.

    Minimal usage (zero config):
        from seeka import Memory
        mem = Memory("./my.db")
        mem.add("User prefers pour-over coffee")
        results = mem.search("coffee preference")

    Full configuration:
        mem = Memory(
            "./my.db",
            embedding_uri="https://api.openai.com/v1",
            embedding_api_key="sk-...",
            llm_uri="https://api.openai.com/v1",
            llm_api_key="sk-...",
            rerank_uri="https://api.cohere.ai/v1",
            rerank_api_key="...",
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
        self._embedding = self._build_embedding(embedding_uri, embedding_api_key)
        self._processor = self._build_processor(llm_uri, llm_api_key)
        self._reranker = self._build_reranker(rerank_uri, rerank_api_key)

    # ------------------------------------------------------------------
    # Component factories
    # ------------------------------------------------------------------

    def _build_embedding(self, uri: str, api_key: str) -> EmbeddingBase:
        if uri and api_key:
            return OpenAIEmbedding(api_key=api_key, base_url=uri)
        return LocalEmbedding()

    def _build_processor(self, uri: str, api_key: str):
        if uri and api_key:
            return AgentProcessor(llm_uri=uri, llm_api_key=api_key)
        return None

    def _build_reranker(self, uri: str, api_key: str):
        # rerank_uri / rerank_api_key reserved for future remote rerank service integration
        if uri or api_key:
            # TODO: integrate remote rerank service
            pass
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, content: str, metadata: dict = None) -> str:
        """
        Store a memory entry and return the first generated id.
        If a processor is configured, content is processed into one or more Memo objects;
        each is stored independently. Without a processor, content is stored as a single Memo.
        """
        if self._processor:
            memos = self._processor.process(content)
        else:
            memos = [Memo(content=content)]

        first_id = None
        for memo in memos:
            fid = str(uuid.uuid4())
            embedding = self._embedding.embed(memo.content)
            self._storage.add(
                id=fid,
                content=memo.content,
                embedding=embedding,
                namespace=self._namespace,
                metadata=metadata or {},
            )
            if first_id is None:
                first_id = fid

        return first_id

    def search(self, query: str, n: int = 5) -> list[dict]:
        """
        Semantic search; returns the top-n most relevant memory entries.
        If a reranker is configured, results are re-ranked after the initial vector search.
        """
        embedding = self._embedding.embed(query)
        results = self._storage.search(
            embedding=embedding,
            namespace=self._namespace,
            n=n if not self._reranker else n * 3,
        )

        if self._reranker and results:
            docs = [r.get("content", "") for r in results]
            ranked_indices = self._reranker.rerank(query, docs)
            results = [results[i] for i in ranked_indices[:n]]

        return results

    def delete(self, id: str) -> None:
        self._storage.delete(id)
