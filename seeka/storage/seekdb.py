from .base import StorageBase


class SeekDB(StorageBase):
    """
    Storage implementation backed by pyseekdb.
    namespace maps to collection name.
    """

    def __init__(self, path: str):
        import pyseekdb
        self._client = pyseekdb.Client(path)

    def add(
        self,
        id: str,
        content: str,
        embedding: list[float],
        namespace: str,
        metadata: dict,
    ) -> None:
        collection = self._client.collection(namespace)
        collection.add(
            id=id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )

    def search(
        self,
        embedding: list[float],
        namespace: str,
        n: int,
    ) -> list[dict]:
        collection = self._client.collection(namespace)
        return collection.search(embedding=embedding, n=n)

    def delete(self, id: str) -> None:
        self._client.delete(id)
