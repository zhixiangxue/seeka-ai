from abc import ABC, abstractmethod

from ..models import Entity, Triple


class GraphBase(ABC):
    """Abstract interface for graph storage backends.

    Implementations handle entity/edge persistence and raw query execution.
    The interface is intentionally thin — higher-level operations like
    entity resolution and temporal conflict handling live in processors.
    """

    @abstractmethod
    async def add_entities(self, entities: list[Entity]) -> None:
        """Persist entities to the graph. Skips duplicates by id."""
        ...

    @abstractmethod
    async def add_edges(self, edges: list[Triple]) -> None:
        """Persist directed edges between existing entities."""
        ...

    @abstractmethod
    async def query(self, statement: str) -> list[dict]:
        """Execute a raw query in the backend's native language.

        Returns a list of row dicts (column_name -> value).
        """
        ...

    @abstractmethod
    async def get_entity_catalog(self) -> list[dict]:
        """Return all entities as [{id, name, type, description}].

        Used by StatementGenerator to inject context into LLM prompts.
        """
        ...

    @abstractmethod
    async def get_predicate_catalog(self) -> list[str]:
        """Return distinct predicate strings currently in the graph."""
        ...

    @abstractmethod
    async def invalidate_edges(
        self, subject_id: str, predicate: str, object_id: str, timestamp: int
    ) -> int:
        """Mark active edges (valid_to=0) matching the pattern as invalidated.

        Sets valid_to = timestamp on matching edges.
        Returns the count of invalidated edges.
        """
        ...

    @abstractmethod
    async def find_active_edges(
        self, subject_id: str, object_id: str, predicates: list[str] | None = None
    ) -> list[dict]:
        """Find currently valid edges (valid_to=0) between subject and object.

        If predicates is provided, only return edges whose predicate is in the list.
        Returns [{predicate, description, valid_from, source_memo_id}].
        """
        ...

    @abstractmethod
    async def delete_entities(self, entity_ids: list[str]) -> None:
        """Delete entities by id. Caller must ensure edges are removed first."""
        ...

    @abstractmethod
    async def update_entity_aliases(self, entity_id: str, aliases: str) -> None:
        """Update the aliases field of an entity."""
        ...

    @abstractmethod
    async def forget(self) -> None:
        """Drop all entities and edges for the bound namespace."""
        ...
