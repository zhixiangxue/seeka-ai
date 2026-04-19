from .base import EmbeddingBase

_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class BailianEmbedding(EmbeddingBase):
    """
    Alibaba Bailian (DashScope) embedding via OpenAI-compatible endpoint.
    Supports native batch: all texts in a single API call.
    Default model: text-embedding-v3 (1536-dim).
    """

    DEFAULT_MODEL = "text-embedding-v3"

    def __init__(self, model: str = None, api_key: str = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, base_url=_BASE_URL)
        self._model = model or self.DEFAULT_MODEL

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Single API call for all texts — much faster than N concurrent calls."""
        if not texts:
            return []
        response = await self._client.embeddings.create(input=texts, model=self._model)
        # sort by index to guarantee order matches input
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
