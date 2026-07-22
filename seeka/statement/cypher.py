"""Cypher dialect statement generator.

Produces Cypher queries from natural language using an LLM. Supports
backend-specific dialect notes (e.g. NeuG quirks vs standard Neo4j).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .base import StatementGenerator


# ---------------------------------------------------------------------------
# NeuG-specific dialect notes — inject into system prompt when using NeuG
# ---------------------------------------------------------------------------

NEUG_DIALECT_NOTES = """\
## Backend: NeuG (Kuzu-derived, v0.1)

IMPORTANT constraints for this Cypher dialect:
1. NO parameterized queries — all values must be inlined as literals.
2. NO startNode() / endNode() functions — use explicit MATCH patterns instead.
3. Reserved words that CANNOT be used as aliases: desc, from, to, order, limit, match, return, where, create, delete, set, merge.
4. ONLY scalar property types (STRING, INT64, DOUBLE, BOOL). No arrays, lists, or maps.
5. Always use AS aliases for RETURN columns — never rely on auto-generated names.
6. String literals use single quotes: 'value', not "value".
7. NEVER use DISTINCT on relationship queries — it causes a runtime crash. Deduplicate in application code if needed.
8. The graph schema has:
   - Node table: Entity(id STRING PK, name STRING, type STRING, description STRING, aliases STRING, namespace STRING, created_at INT64)
   - Rel table: RELATES(predicate STRING, description STRING, source_memo_id STRING, valid_from INT64, valid_to INT64, created_at INT64)
   - An edge with valid_to = 0 is currently active; valid_to > 0 means invalidated.
"""


class _CypherOutput(BaseModel):
    """Structured output from the LLM for Cypher generation."""
    reasoning: str = Field(description="Brief explanation of how you mapped the query to Cypher")
    cypher: str = Field(description="The generated Cypher query, ready to execute")


class CypherGenerator(StatementGenerator):
    """LLM-powered natural language to Cypher query generator.

    Args:
        model_uri: chak-format model URI (e.g. 'deepseek/deepseek-chat').
        api_key: API key for the LLM provider.
        dialect_notes: Backend-specific Cypher quirks injected into the
            system prompt. Use NEUG_DIALECT_NOTES for NeuG backends.
    """

    dialect = "cypher"

    _SYSTEM_PROMPT = """\
You are a Cypher query generator. Given a natural language question and a catalog of entities/predicates in the graph, produce a valid Cypher query that answers the question.

## Rules
1. ONLY use entities and predicates from the provided catalog.
2. Match entity names case-insensitively (use toLower() or CONTAINS when appropriate).
3. For relationship queries, always filter by valid_to = 0 (currently active edges) unless the user asks about historical/invalidated data.
4. Return human-readable columns with clear AS aliases.
5. If the question cannot be answered with the available catalog, return a query that returns an empty result with a comment explaining why.
6. Keep queries simple — prefer single MATCH patterns over complex subqueries.

{dialect_notes}
"""

    def __init__(self, model_uri: str, api_key: str, dialect_notes: str = ""):
        self._model_uri = model_uri
        self._api_key = api_key
        self._dialect_notes = dialect_notes

    async def generate(
        self,
        query: str,
        entity_catalog: list[dict],
        predicate_catalog: list[str],
    ) -> str:
        """Convert natural language to a Cypher query string via LLM."""
        from chak import Conversation

        system = self._SYSTEM_PROMPT.format(
            dialect_notes=self._dialect_notes if self._dialect_notes else ""
        )

        # Build the user message with catalog context
        catalog_lines = []
        for ent in entity_catalog:
            catalog_lines.append(
                f"  - [{ent['type']}] {ent['name']} (id: {ent['id']})"
                + (f" — {ent['description']}" if ent.get('description') else "")
            )
        entity_section = "\n".join(catalog_lines) if catalog_lines else "  (empty)"

        pred_section = ", ".join(predicate_catalog) if predicate_catalog else "(none)"

        user_message = (
            f"## Entity Catalog\n{entity_section}\n\n"
            f"## Available Predicates\n  {pred_section}\n\n"
            f"## Question\n{query}"
        )

        conv = Conversation(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=system,
        )
        result = await conv.asend(user_message, returns=_CypherOutput)
        if result is None:
            raise RuntimeError(
                "CypherGenerator: LLM returned None. "
                "Check API key / model availability."
            )
        return result.cypher
