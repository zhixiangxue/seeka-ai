import importlib.util
import inspect
import os

from pydantic import BaseModel

from ..models import Memo
from .base import ProcessorBase


class _MemoList(BaseModel):
    """Internal structured output schema used by chak to extract Memo contents."""

    memos: list[str]


class AgenticProcessor(ProcessorBase):
    """
    Agent-driven processor backed by chak.Conversation.
    model_uri follows chak URI format: 'provider/model' or 'provider@base_url:model'.
    """

    SYSTEM_PROMPT = (
        "You are a memory extraction assistant. "
        "Given the input content, extract concise, self-contained memory fragments. "
        "Each fragment must be a single clear statement. "
        "Return a structured list of fragments."
    )

    def __init__(self, model_uri: str, api_key: str):
        self._model_uri = model_uri
        self._api_key = api_key
        self._tools = self._load_skills()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_skills(self) -> list:
        """
        Discover and load all skills from the skills/ directory.

        Handles four tool types:
        - Sub-directory with SKILL.md  → ClaudeSkill
        - .py file: SkillBase subclass → instantiate directly (same as plain object)
        - .py file: plain class        → instantiate directly
        - .py file: plain function     → pass directly

        All tool types are passed directly to chak Conversation without pre-wrapping.
        """
        from chak.tools.skills import ClaudeSkill

        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        tools = []

        for entry in os.listdir(skills_dir):
            entry_path = os.path.join(skills_dir, entry)

            # Claude skill pack: directory containing SKILL.md
            if os.path.isdir(entry_path):
                skill_md = os.path.join(entry_path, "SKILL.md")
                if os.path.exists(skill_md):
                    tools.append(ClaudeSkill(entry_path))
                continue

            # Python skill file
            if not entry.endswith(".py") or entry.startswith("_"):
                continue

            module = self._import_file(entry_path, entry[:-3])

            for name in dir(module):
                if name.startswith("_"):
                    continue
                attr = getattr(module, name)

                if isinstance(attr, type):
                    # Only instantiate classes defined in this file
                    if getattr(attr, "__module__", "") == module.__name__:
                        tools.append(attr())
                elif inspect.isfunction(attr):
                    # Only functions defined in this file
                    if getattr(attr, "__module__", "") == module.__name__:
                        tools.append(attr)

        return tools

    @staticmethod
    def _import_file(path: str, module_name: str):
        """Dynamically import a Python file as a module."""
        spec = importlib.util.spec_from_file_location(
            f"seeka.processor.skills.{module_name}", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _make_conversation(self):
        """Create a fresh single-shot chak Conversation."""
        from chak import Conversation

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
        import asyncio
        conv = self._make_conversation()
        result = await asyncio.to_thread(conv.send, content, _MemoList)
        return [Memo(content=text) for text in result.memos]
