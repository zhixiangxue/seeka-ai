from .base import EmbeddingBase


class OpenAIEmbedding(EmbeddingBase):
    """
    Call the OpenAI Embedding API.
    base_url supports any OpenAI-compatible third-party service.
    """

    DEFAULT_MODEL = "text-embedding-3-small"

    def __init__(self, api_key: str, base_url: str = None, model: str = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model or self.DEFAULT_MODEL

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding
