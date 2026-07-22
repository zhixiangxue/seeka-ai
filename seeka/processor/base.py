from abc import ABC, abstractmethod

from ..models import Memo, Entity, Triple


class ProcessorBase(ABC):

    @abstractmethod
    async def process(self, content: str) -> tuple[list[Memo], list[Entity], list[Triple]]:
        """
        Accept raw content and return extracted memories + graph data.

        Returns:
            A tuple of (memos, entities, triples).
            - memos: list of Memo objects (only content filled; id/namespace assigned later)
            - entities: list of Entity objects for the knowledge graph (may be empty)
            - triples: list of Triple objects (directed edges) for the graph (may be empty)
        """
        ...
