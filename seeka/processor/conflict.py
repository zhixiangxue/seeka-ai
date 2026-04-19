from pydantic import BaseModel

from ..models import Memo


class _ConflictResult(BaseModel):
    """Structured output schema for conflict detection."""
    conflicting_ids: list[str]


class _MemoConflict(BaseModel):
    new_id: str
    conflicting_ids: list[str]


class _BatchConflictResult(BaseModel):
    results: list[_MemoConflict]


class ConflictResolver:
    """
    LLM-powered conflict detector.

    Before each new Memo is written to storage, scan the semantically
    nearest existing Memos and delete any that are directly contradicted
    or superseded by the new one.

    Only hard, unambiguous contradictions are flagged — e.g.
      "user likes coffee"  vs  "user stopped drinking coffee"
    Complementary or merely similar memories are left untouched.
    """

    SYSTEM_PROMPT = (
        "You are a memory conflict detector. "
        "Given a list of NEW memory statements and a list of EXISTING memory statements "
        "(each prefixed with its ID in brackets), "
        "identify which existing memories are directly contradicted or superseded "
        "by each new memory. "
        "Only flag CLEAR, DIRECT contradictions. "
        "Do NOT flag memories that are complementary, additive, or merely similar. "
        "Return results per new memory ID. "
        "If a new memory has no conflicts, omit it or return an empty conflicting_ids list."
    )

    def __init__(self, model_uri: str, api_key: str):
        self._model_uri = model_uri
        self._api_key = api_key

    def _make_conversation(self):
        from chak import Conversation
        return Conversation(
            model_uri=self._model_uri,
            api_key=self._api_key,
            system_prompt=self.SYSTEM_PROMPT,
        )

    async def resolve_batch(
        self,
        new_memos: list[Memo],
        all_candidates: list[Memo],
    ) -> dict[str, list[str]]:
        """
        Batch conflict detection: one LLM call for all new memos at once.
        Returns {new_memo_id: [existing_ids_to_delete]}.
        """
        if not new_memos or not all_candidates:
            return {}

        lines = ["NEW MEMORIES:"]
        for m in new_memos:
            lines.append(f"  [{m.id}] {m.content}")
        lines.append("")
        lines.append("EXISTING MEMORIES:")
        for c in all_candidates:
            lines.append(f"  [{c.id}] {c.content}")
        prompt = "\n".join(lines)

        conv = self._make_conversation()
        result = await conv.asend(prompt, returns=_BatchConflictResult)
        if result is None:
            return {}

        valid_existing = {c.id for c in all_candidates}
        out: dict[str, list[str]] = {}
        for item in result.results:
            if item.new_id not in {m.id for m in new_memos}:
                continue  # 防LLM幻觉出不存在的new_id
            out[item.new_id] = [i for i in item.conflicting_ids if i in valid_existing]
        return out

    async def resolve(self, new_memo: Memo, candidates: list[Memo]) -> list[str]:
        """Single-memo convenience wrapper around resolve_batch."""
        result = await self.resolve_batch([new_memo], candidates)
        return result.get(new_memo.id, [])
