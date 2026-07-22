import os

from pydantic import BaseModel, Field

from ..models import Memo, Entity, Triple
from .base import ProcessorBase


# ---------------------------------------------------------------------------
# LLM structured output schemas
# ---------------------------------------------------------------------------

class _Memo(BaseModel):
    """Lean schema for LLM output — only content, no embedding/id/timestamp."""
    content: str = Field(description="A self-contained memory or preference statement")


class _MemoList(BaseModel):
    """Schema when graph is disabled — memos only (saves tokens)."""
    memos: list[_Memo]


class _ProcessResult(BaseModel):
    """Schema when graph is enabled — memos + entities + triples in one LLM call."""
    memos: list[_Memo]
    entities: list[Entity] = []   # LLM fills: id, name, type, description
    triples: list[Triple] = []   # LLM fills: subject_id, predicate, object_id, description


# ---------------------------------------------------------------------------
# Default graph extraction prompt (used when no skill provides ## Graph Extraction)
# ---------------------------------------------------------------------------

_DEFAULT_GRAPH_PROMPT = """

## Graph Extraction

In addition to memory statements, extract a knowledge graph from the input:

### Entities
Extract meaningful entities: person, place, thing, concept, activity, etc.
Each entity needs: id (short slug like 'pour-over-coffee'), name, type, description.

### Triples (Edges)
Extract directed relationships between entities.
Each triple needs: subject_id, predicate (verb phrase), object_id, description.
Use natural-language predicates: likes, drinks, experiences, practices, alleviates, etc.

### Rules
- Entity ids should be short, lowercase, hyphen-separated slugs.
- Only extract entities that participate in at least one triple.
- Predicates should be concise verb phrases (1-3 words).
- Do NOT extract vague time expressions or pure adjectives as entities.
"""


class AgenticProcessor(ProcessorBase):
    """
    Agent-driven processor backed by chak.Conversation.
    model_uri follows chak URI format: 'provider/model' or 'provider@base_url:model'.

    When graph_enabled=True, the LLM extracts both memos and graph data
    (entities + triples) in a single call.
    """

    SYSTEM_PROMPT = (
        "You are a memory extraction assistant. "
        "Analyze the input and extract memory fragments. "
        "Return a structured list of fragments."
    )

    def __init__(
        self,
        model_uri: str,
        api_key: str,
        skills: list[str] | None = None,
        graph_enabled: bool = False,
    ):
        self._model_uri = model_uri
        self._api_key = api_key
        self._skill_dirs = [os.path.abspath(d) for d in (skills or [])]
        self._graph_enabled = graph_enabled
        self._tools = None  # lazy-loaded on first LLM call

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_skills(self) -> list:
        """
        Load ClaudeSkill instances from the provided skill directories.
        Each directory must contain a SKILL.md file.
        """
        from chak.tools.skills import ClaudeSkill
        return [ClaudeSkill(d) for d in self._skill_dirs]

    def _get_graph_prompt(self) -> str:
        """Get graph extraction prompt from skills or use default.

        Scans skill directories for a SKILL.md containing a '## Graph Extraction'
        section. If found, uses that; otherwise falls back to the built-in default.
        """
        for skill_dir in self._skill_dirs:
            skill_path = os.path.join(skill_dir, "SKILL.md")
            if os.path.isfile(skill_path):
                with open(skill_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Look for ## Graph Extraction section
                marker = "## Graph Extraction"
                idx = content.find(marker)
                if idx != -1:
                    # Extract from marker to end of file or next top-level heading
                    section = content[idx:]
                    # Find next ## heading (not ### or deeper)
                    lines = section.split("\n")
                    end_lines = []
                    for i, line in enumerate(lines):
                        if i == 0:
                            end_lines.append(line)
                            continue
                        if line.startswith("## ") and not line.startswith("### "):
                            break
                        end_lines.append(line)
                    return "\n\n" + "\n".join(end_lines)
        return _DEFAULT_GRAPH_PROMPT

    def _make_conversation(self):
        """Create a fresh single-shot chak Conversation."""
        from chak import Conversation

        if self._tools is None:
            self._tools = self._load_skills()

        system = self.SYSTEM_PROMPT
        if self._graph_enabled:
            system += self._get_graph_prompt()

        kwargs = dict(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=system,
        )
        if self._tools:
            kwargs["tools"] = self._tools
        return Conversation(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def process(self, content: str) -> tuple[list[Memo], list[Entity], list[Triple]]:
        """
        Extract memories (and optionally graph data) from raw content via LLM.

        Returns:
            (memos, entities, triples) — entities and triples are empty
            when graph_enabled=False.
        """
        import logging
        logging.getLogger("chak").setLevel(logging.DEBUG)

        conv = self._make_conversation()

        if self._graph_enabled:
            result = await conv.asend(content, returns=_ProcessResult)
            if result is None:
                raise RuntimeError(
                    "AgenticProcessor: LLM returned None for _ProcessResult. "
                    "Check API key / network / model support."
                )
            memos = [Memo(content=item.content) for item in result.memos]
            return memos, list(result.entities), list(result.triples)
        else:
            result = await conv.asend(content, returns=_MemoList)
            if result is None:
                raise RuntimeError(
                    "AgenticProcessor: LLM returned None for _MemoList. "
                    "Check API key / network / model support."
                )
            memos = [Memo(content=item.content) for item in result.memos]
            return memos, [], []
