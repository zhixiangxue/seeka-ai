from abc import ABC, abstractmethod


class StatementGenerator(ABC):
    """Abstract interface for natural-language-to-graph-query generation.

    Each implementation targets a specific query dialect (Cypher, Gremlin,
    SPARQL, etc.). The generator only produces the query string — execution
    is handled by the caller via GraphBase.query().

    This decoupling allows the same StatementGenerator to be tested without
    a live database, and lets different graph backends share the same LLM
    generation logic when their dialects overlap.
    """

    @property
    @abstractmethod
    def dialect(self) -> str:
        """The query language this generator targets (e.g. 'cypher', 'gremlin')."""
        ...

    @abstractmethod
    async def generate(
        self,
        query: str,
        entity_catalog: list[dict],
        predicate_catalog: list[str],
    ) -> str:
        """Convert a natural language query into a graph query string.

        Args:
            query: The user's natural language question.
            entity_catalog: List of {id, name, type, description} dicts
                representing entities currently in the graph.
            predicate_catalog: List of distinct predicate strings available.

        Returns:
            A query string in the target dialect, ready for execution.
        """
        ...
