from abc import ABC, abstractmethod


class RerankBase(ABC):

    @abstractmethod
    def rerank(self, query: str, docs: list[str]) -> list[int]:
        """
        Accept a query and candidate docs; return indices sorted by relevance (most relevant first).
        """
        ...
