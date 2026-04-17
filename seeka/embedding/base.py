from abc import ABC, abstractmethod


class EmbeddingBase(ABC):

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...
