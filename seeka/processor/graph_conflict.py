"""Temporal conflict detection for knowledge graph triples.

Detects when incoming triples conflict with existing active edges in the
graph, using predicate similarity heuristics + LLM classification.

Pipeline position: runs AFTER entity resolution but BEFORE writing triples,
so that conflicting old edges can be invalidated instead of creating
contradictory parallel facts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models import Triple
from ..graph.base import GraphBase


class _ConflictJudgment(BaseModel):
    """LLM output for temporal conflict classification."""
    is_conflict: bool = Field(
        description="True if the new triple contradicts/supersedes the existing one"
    )
    conflict_type: str = Field(
        description=(
            "'evolution' (preference changed), 'correction' (fact was wrong), "
            "'complement' (additional info), or 'duplicate' (same fact restated)"
        )
    )
    reasoning: str = Field(description="Brief explanation")


_SYSTEM_PROMPT = """\
You are a temporal conflict detector for a knowledge graph memory system.

Given an EXISTING edge and a NEW edge (both connecting the same or related entities),
determine if they conflict.

Conflict types:
- "evolution": The user's preference/state has CHANGED over time. The old fact was true
  before but is no longer true. Example: "dislikes milk tea" → "likes milk tea"
- "correction": The old fact was WRONG and the new one corrects it.
  Example: "Blue Bottle is in Shinjuku" → "Blue Bottle is in Shibuya"
- "complement": The new fact ADDS information without contradicting the old.
  Example: "learning guitar" + "practicing chord transitions" — both can coexist.
- "duplicate": The new fact is essentially the SAME as the existing one, just reworded.
  Example: "loves pour-over coffee" + "loves pour-over coffee" — no change needed.

Rules:
- If predicates are antonyms (likes/dislikes, started/stopped), it's likely "evolution".
- If same predicate + same object but different description, check if descriptions conflict.
- Be conservative: only mark as conflict if genuinely contradictory.
"""

# Predicate groups — predicates within the same group may conflict with each other
_SIMILAR_PREDICATES: dict[str, set[str]] = {
    "likes": {"likes", "loves", "dislikes", "hates", "prefers", "avoids"},
    "loves": {"likes", "loves", "dislikes", "hates", "prefers", "avoids"},
    "dislikes": {"likes", "loves", "dislikes", "hates", "prefers", "avoids"},
    "hates": {"likes", "loves", "dislikes", "hates", "prefers", "avoids"},
    "prefers": {"likes", "loves", "dislikes", "prefers", "avoids", "chooses_over"},
    "avoids": {"likes", "loves", "dislikes", "prefers", "avoids"},
    "frequents": {"frequents", "visits", "goes_to", "stopped", "avoids"},
    "stopped": {"frequents", "visits", "goes_to", "stopped", "started"},
    "started": {"started", "stopped", "learning", "practicing"},
    "learning": {"learning", "practicing", "studying", "stopped", "quit"},
    "practicing": {"learning", "practicing", "studying", "stopped", "quit"},
    "values": {"values", "prioritizes", "ignores"},
    "lives_in": {"lives_in", "moved_to", "moved_from"},
    "works_at": {"works_at", "left", "quit"},
}


def _get_related_predicates(predicate: str) -> list[str]:
    """Get the set of predicates that might conflict with the given one."""
    group = _SIMILAR_PREDICATES.get(predicate)
    if group:
        return list(group)
    # If not in known groups, only look for exact match
    return [predicate]


class TripleConflictResolver:
    """Detect temporal conflicts between new and existing graph edges.

    For each incoming triple, checks if an active edge with a related
    predicate already connects the same pair of entities. If found, uses
    LLM to classify the conflict type and decide whether to invalidate
    the old edge.

    Args:
        model_uri: chak-format model URI for LLM judgment.
        api_key: API key for the LLM provider.
    """

    def __init__(self, model_uri: str, api_key: str):
        self._model_uri = model_uri
        self._api_key = api_key

    def _make_conversation(self):
        from chak import Conversation
        return Conversation(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=_SYSTEM_PROMPT,
        )

    async def detect(
        self,
        new_triples: list[Triple],
        graph: GraphBase,
    ) -> tuple[list[Triple], list[dict]]:
        """Detect conflicts between new triples and existing active edges.

        Returns:
            - triples_to_write: edges that should be persisted (excludes duplicates)
            - invalidations: list of {subject_id, predicate, object_id} dicts
              identifying old edges that should be invalidated before writing
        """
        if not new_triples:
            return [], []

        triples_to_write: list[Triple] = []
        invalidations: list[dict] = []
        conv = self._make_conversation()

        for triple in new_triples:
            # Find potentially conflicting active edges
            related_preds = _get_related_predicates(triple.predicate)
            existing = await graph.find_active_edges(
                triple.subject_id, triple.object_id, related_preds
            )

            if not existing:
                # No potential conflicts — safe to write
                triples_to_write.append(triple)
                continue

            # Ask LLM to judge the top existing edge
            ext = existing[0]
            prompt = (
                f"EXISTING edge:\n"
                f"  subject_id={triple.subject_id} ──{ext['predicate']}──▶ object_id={triple.object_id}\n"
                f"  Description: \"{ext['description']}\"\n"
                f"  Valid since: {ext['valid_from']}\n\n"
                f"NEW edge:\n"
                f"  subject_id={triple.subject_id} ──{triple.predicate}──▶ object_id={triple.object_id}\n"
                f"  Description: \"{triple.description}\"\n\n"
                f"Is this a conflict? If so, what type?"
            )

            try:
                judgment = await conv.asend(prompt, returns=_ConflictJudgment)
                if judgment is None:
                    # Fail open: write the new edge
                    triples_to_write.append(triple)
                    continue

                if judgment.is_conflict and judgment.conflict_type in ("evolution", "correction"):
                    # Invalidate old edge, write new one
                    invalidations.append({
                        "subject_id": triple.subject_id,
                        "predicate": ext["predicate"],
                        "object_id": triple.object_id,
                    })
                    triples_to_write.append(triple)
                elif judgment.conflict_type == "duplicate":
                    # Skip — already exists in equivalent form
                    pass
                else:
                    # complement — write alongside existing
                    triples_to_write.append(triple)

            except Exception:
                # Fail open: write the new edge on any error
                triples_to_write.append(triple)

        return triples_to_write, invalidations
