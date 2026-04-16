from abc import ABC, abstractmethod


class EmbeddingBase(ABC):

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        ...
