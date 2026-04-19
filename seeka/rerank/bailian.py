from .base import RerankBase
from ..utils.uri import parse as parse_uri


class BailianRerank(RerankBase):
    """
    Rerank via Alibaba Bailian (DashScope) TextReRank API.
    model_uri follows chak URI format: 'bailian/qwen3-rerank'.
    Requires DASHSCOPE_API_KEY or explicit api_key.
    """

    DEFAULT_MODEL = "qwen3-rerank"

    def __init__(self, model_uri: str, api_key: str):
        import dashscope
        parsed = parse_uri(model_uri)
        self._model = parsed.get("model") or self.DEFAULT_MODEL
        self._api_key = api_key
        dashscope.api_key = api_key

    async def rerank(self, query: str, docs: list[str]) -> list[int]:
        import asyncio
        from http import HTTPStatus
        import dashscope

        def _call():
            return dashscope.TextReRank.call(
                model=self._model,
                query=query,
                documents=docs,
                top_n=len(docs),
                return_documents=False,
            )

        resp = await asyncio.to_thread(_call)
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"Bailian rerank failed [{resp.status_code}]: {resp.message}"
            )

        ranked = sorted(resp.output.results, key=lambda r: r.relevance_score, reverse=True)
        return [r.index for r in ranked]
