import asyncio

from ..models import Memo
from .base import StorageBase


class SeekDB(StorageBase):
    """
    Storage implementation backed by pyseekdb.
    namespace maps to collection name.
    """

    def __init__(self, path: str):
        import pyseekdb
        self._client = pyseekdb.Client(path)

    def _collection(self, namespace: str):
        return self._client.get_or_create_collection(namespace)

    async def add(self, memo: Memo, embedding: list[float]) -> None:
        def _add():
            col = self._collection(memo.namespace)
            col.add(
                ids=memo.id,
                documents=memo.content,
                embeddings=embedding,
                metadatas=memo.metadata or {},
            )
        await asyncio.to_thread(_add)

    async def search(
        self,
        embedding: list[float],
        namespace: str,
        n: int,
    ) -> list[dict]:
        def _search():
            col = self._collection(namespace)
            result = col.query(query_embeddings=embedding, n_results=n)
            ids = result.get("ids", [[]])[0]
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            return [
                {"id": i, "content": d, "metadata": m}
                for i, d, m in zip(ids, docs, metas)
            ]
        return await asyncio.to_thread(_search)

    async def delete(self, id: str, namespace: str) -> None:
        def _delete():
            col = self._collection(namespace)
            col.delete(ids=id)
        await asyncio.to_thread(_delete)
