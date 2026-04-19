from ..models import Memo
from .base import StorageBase


class SeekDB(StorageBase):
    """
    Storage implementation backed by pyseekdb.
    namespace maps to collection name.

    NOTE: pyseekdb (OceanBase) connections are NOT thread-safe.
    All operations are called synchronously in the event loop thread.
    The actual operations (query/add/delete) are <100ms so this is fine.
    """

    def __init__(self, path: str, namespace: str):
        import pyseekdb
        self._client = pyseekdb.Client(path)
        self._namespace = namespace

    def _collection(self, dimension: int = None):
        """Get existing collection, or create it with the correct vector dimension.
        
        We deliberately separate get vs create:
        - get_collection: no extra params, honours whatever config was stored
        - create_collection: explicit dimension + embedding_function=None
          (avoids the dimension vs default-384-ef conflict)
        """
        try:
            return self._client.get_collection(self._namespace)
        except Exception:
            # Collection doesn't exist yet — create with correct dimension
            if dimension is not None:
                from pyseekdb.client.configuration import HNSWConfiguration
                config = HNSWConfiguration(dimension=dimension)
                return self._client.create_collection(
                    self._namespace, configuration=config, embedding_function=None
                )
            return self._client.create_collection(self._namespace)

    async def add(self, memo: Memo) -> None:
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        col = self._collection(dimension=len(memo.embedding))
        col.add(
            ids=memo.id,
            documents=memo.content,
            embeddings=memo.embedding,
            metadatas=memo.metadata or {},
        )

    async def add_batch(self, memos: list[Memo]) -> None:
        if not memos:
            return
        if any(m.embedding is None for m in memos):
            raise ValueError("All Memos must have embedding set before add_batch")
        col = self._collection(dimension=len(memos[0].embedding))
        col.add(
            ids=[m.id for m in memos],
            documents=[m.content for m in memos],
            embeddings=[m.embedding for m in memos],
            metadatas=[m.metadata or {} for m in memos],
        )

    async def search(self, embedding: list[float], n: int, filter: dict | None = None) -> list[dict]:
        col = self._collection(dimension=len(embedding))
        total = col.count()
        if total == 0:
            return []  # 空集合不查询，避免 OB_INVALID_ARGUMENT
        actual_n = min(n, total)
        result = col.query(
            query_embeddings=embedding,
            n_results=actual_n,
            where=filter,
        )
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        return [
            {"id": i, "content": d, "metadata": m}
            for i, d, m in zip(ids, docs, metas)
        ]

    async def delete(self, id: str) -> None:
        col = self._collection()
        col.delete(ids=id)

    async def update(self, memo: Memo) -> None:
        """Replace a Memo's content, embedding and metadata in-place (delete + re-add)."""
        if memo.embedding is None:
            raise ValueError(f"Memo {memo.id} has no embedding set")
        col = self._collection(dimension=len(memo.embedding))
        col.delete(ids=memo.id)
        col.add(
            ids=memo.id,
            documents=memo.content,
            embeddings=memo.embedding,
            metadatas=memo.metadata or {},
        )

    async def forget(self) -> None:
        try:
            self._client.delete_collection(self._namespace)
        except Exception:
            pass  # 集合不存在时直接忽略
