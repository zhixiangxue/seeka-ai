from abc import ABC, abstractmethod


class StorageBase(ABC):

    @abstractmethod
    def add(
        self,
        id: str,
        content: str,
        embedding: list[float],
        namespace: str,
        metadata: dict,
    ) -> None:
        ...

    @abstractmethod
    def search(
        self,
        embedding: list[float],
        namespace: str,
        n: int,
    ) -> list[dict]:
        ...

    @abstractmethod
    def delete(self, id: str) -> None:
        ...
