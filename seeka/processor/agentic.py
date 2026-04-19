import os

from pydantic import BaseModel, Field

from ..models import Memo
from .base import ProcessorBase


class _MemoItem(BaseModel):
    content: str = Field(description="A self-contained memory or preference statement")


class _MemoList(BaseModel):
    """Internal structured output schema used by chak to extract Memo contents."""

    memos: list[_MemoItem]


class AgenticProcessor(ProcessorBase):
    """
    Agent-driven processor backed by chak.Conversation.
    model_uri follows chak URI format: 'provider/model' or 'provider@base_url:model'.
    """

    SYSTEM_PROMPT = (
        "You are a memory extraction assistant. "
        "Analyze the input and extract memory fragments. "
        "Return a structured list of fragments."
    )

    def __init__(self, model_uri: str, api_key: str, skills: list[str] | None = None):
        self._model_uri = model_uri
        self._api_key = api_key
        self._skill_dirs = [os.path.abspath(d) for d in (skills or [])]
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

    def _make_conversation(self):
        """Create a fresh single-shot chak Conversation. Also lazy-loads skills and chak on first call."""
        from chak import Conversation

        if self._tools is None:
            self._tools = self._load_skills()

        kwargs = dict(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=self.SYSTEM_PROMPT,
        )
        if self._tools:
            kwargs["tools"] = self._tools
        return Conversation(**kwargs)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def process(self, content: str) -> list[Memo]:
        """
        Extract Memo objects from raw content via LLM + skills.
        Returns a list of Memo instances with only content filled in.
        """
        import logging
        # 把 chak 的 warning 输出到 stderr，方便排查
        logging.getLogger("chak").setLevel(logging.DEBUG)

        conv = self._make_conversation()
        result = await conv.asend(content, returns=_MemoList)
        if result is None:
            raise RuntimeError(
                "AgenticProcessor: asend(returns=_MemoList) returned None. "
                "Likely cause: structured output call failed (check API key / network / model support). "
                "See chak logger output above for details."
            )
        return [Memo(content=item.content) for item in result.memos]
