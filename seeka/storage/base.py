from abc import ABC, abstractmethod

from ..models import Memo


class StorageBase(ABC):

    @abstractmethod
    async def add(self, memo: Memo, embedding: list[float]) -> None:
        """Persist a fully-populated Memo together with its embedding vector."""
        ...

    @abstractmethod
    async def search(
        self,
        embedding: list[float],
        namespace: str,
        n: int,
    ) -> list[dict]:
        ...

    @abstractmethod
    async def delete(self, id: str, namespace: str) -> None:
        ...
