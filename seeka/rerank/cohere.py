import cohere

from .base import RerankBase
from ..utils.uri import parse as parse_uri


class CohereRerank(RerankBase):
    """
    Rerank via Cohere API.
    model_uri follows chak URI format: 'cohere/rerank-v3.5' or 'cohere@base_url:model'.
    """

    DEFAULT_MODEL = "rerank-v3.5"

    def __init__(self, model_uri: str, api_key: str):
        parsed = parse_uri(model_uri)
        self._model = parsed.get("model") or self.DEFAULT_MODEL
        base_url = parsed.get("base_url")
        self._client = cohere.AsyncClientV2(api_key=api_key, base_url=base_url)

    async def rerank(self, query: str, docs: list[str]) -> list[int]:
        response = await self._client.rerank(
            model=self._model,
            query=query,
            documents=docs,
        )
        ranked = sorted(response.results, key=lambda r: r.relevance_score, reverse=True)
        return [r.index for r in ranked]
