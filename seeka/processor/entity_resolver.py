"""Entity resolution — deduplication during dream write path.

Detects whether incoming entities already exist in the graph under
different names, using embedding similarity + LLM judgment.

Pipeline position: runs BEFORE writing entities to the graph, so that
duplicate nodes are never created.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from ..models import Entity
from ..embedding.base import EmbeddingBase


class _ResolutionJudgment(BaseModel):
    """LLM output for entity resolution."""
    is_same: bool = Field(description="True if the two entities refer to the same real-world concept")
    reasoning: str = Field(description="Brief explanation of the judgment")


_SYSTEM_PROMPT = """\
You are an entity resolution judge. Given two entity descriptions, determine
whether they refer to the SAME real-world concept/thing.

Consider:
- Semantic equivalence (same concept, different wording)
- Type compatibility (a "drink" and an "instrument" are never the same)
- Context overlap (descriptions that complement each other)

Be STRICT: only judge as same if you are confident they refer to the exact
same thing. "Coffee" and "pour-over coffee" are the same drink concept.
"Guitar" and "acoustic guitar" are the same if context confirms it.
"""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EntityResolver:
    """Resolve incoming entities against existing graph entities.

    Uses embedding cosine similarity to find candidates, then LLM to
    confirm whether they are truly the same entity.

    Args:
        embedding: Embedding model for computing name similarity.
        model_uri: chak-format model URI for LLM judgment.
        api_key: API key for the LLM provider.
        threshold: Minimum cosine similarity to consider a candidate match.
    """

    def __init__(
        self,
        embedding: EmbeddingBase,
        model_uri: str,
        api_key: str,
        threshold: float = 0.75,
    ):
        self._embedding = embedding
        self._model_uri = model_uri
        self._api_key = api_key
        self._threshold = threshold

    def _make_conversation(self):
        from chak import Conversation
        return Conversation(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=_SYSTEM_PROMPT,
        )

    async def resolve(
        self,
        new_entities: list[Entity],
        existing_catalog: list[dict],
    ) -> tuple[list[Entity], dict[str, str]]:
        """Resolve new entities against existing graph entities.

        Returns:
            - entities_to_write: only genuinely new entities (not duplicates)
            - id_map: mapping from each new entity's id to its resolved id.
              For merged entities, this maps to the existing entity's id.
              For genuinely new entities, maps to their own id (identity).
        """
        if not new_entities:
            return [], {}

        # Identity map as starting point
        id_map: dict[str, str] = {ent.id: ent.id for ent in new_entities}

        if not existing_catalog:
            # No existing entities to resolve against
            return list(new_entities), id_map

        # Batch embed all entity names for similarity comparison
        existing_names = [e["name"] for e in existing_catalog]
        new_names = [e.name for e in new_entities]
        all_embeddings = await self._embedding.embed_batch(existing_names + new_names)

        n_existing = len(existing_catalog)
        existing_embs = all_embeddings[:n_existing]
        new_embs = all_embeddings[n_existing:]

        entities_to_write: list[Entity] = []
        conv = self._make_conversation()

        for i, new_ent in enumerate(new_entities):
            new_emb = new_embs[i]

            # Find candidates above threshold
            candidates: list[tuple[dict, float]] = []
            for j, ext_ent in enumerate(existing_catalog):
                sim = _cosine_similarity(new_emb, existing_embs[j])
                if sim >= self._threshold:
                    candidates.append((ext_ent, sim))

            candidates.sort(key=lambda x: x[1], reverse=True)

            if not candidates:
                # No similar existing entity — this is genuinely new
                entities_to_write.append(new_ent)
                continue

            # LLM judges the top candidate
            top_candidate, top_sim = candidates[0]
            prompt = (
                f"Entity A: name=\"{new_ent.name}\", type=\"{new_ent.type}\", "
                f"description=\"{new_ent.description}\"\n"
                f"Entity B: name=\"{top_candidate['name']}\", type=\"{top_candidate['type']}\", "
                f"description=\"{top_candidate.get('description', '')}\"\n\n"
                f"Cosine similarity of names: {top_sim:.3f}\n"
                f"Are these the SAME entity?"
            )

            try:
                judgment = await conv.asend(prompt, returns=_ResolutionJudgment)
                if judgment and judgment.is_same:
                    # Merge: map new entity's id to existing entity's id
                    id_map[new_ent.id] = top_candidate["id"]
                else:
                    # Different entity despite high similarity
                    entities_to_write.append(new_ent)
            except Exception:
                # Fail open: treat as new entity if LLM fails
                entities_to_write.append(new_ent)

        return entities_to_write, id_map
