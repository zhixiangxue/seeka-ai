from abc import ABC, abstractmethod

from ..models import Memo


class StorageBase(ABC):

    @abstractmethod
    async def add(self, memo: Memo) -> None:
        """Persist a fully-populated Memo together with its embedding vector."""
        ...

    @abstractmethod
    async def add_batch(self, memos: list[Memo]) -> None:
        """Persist multiple Memos in a single batch operation."""
        ...

    @abstractmethod
    async def search(self, embedding: list[float], n: int, filter: dict | None = None) -> list[dict]:
        """Vector similarity search. filter follows MongoDB-style where syntax."""
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        ...

    @abstractmethod
    async def update(self, memo: Memo) -> None:
        """Replace the content, embedding and metadata of an existing Memo."""
        ...

    @abstractmethod
    async def forget(self) -> None:
        """Drop the entire collection for the bound namespace."""
        ...
