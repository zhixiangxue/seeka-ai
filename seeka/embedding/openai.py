from openai import AsyncOpenAI

from .base import EmbeddingBase
from ..utils.uri import parse as parse_uri


class OpenAIEmbedding(EmbeddingBase):
    """
    OpenAI-compatible embedding via AsyncOpenAI.
    model_uri follows chak URI format: 'provider/model' or 'provider@base_url:model'.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(self, model_uri: str, api_key: str):
        parsed = parse_uri(model_uri)
        self._client = AsyncOpenAI(api_key=api_key, base_url=parsed.get("base_url"))
        self._model = parsed.get("model") or self.DEFAULT_MODEL

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding
