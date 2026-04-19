import asyncio

from .base import EmbeddingBase


class SentenceTransformerEmbedding(EmbeddingBase):
    """
    In-process embedding via sentence-transformers. Lazily loads all-MiniLM-L6-v2 (384-dim, ~80MB).
    Zero config, no external server required.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.MODEL_NAME)

    async def embed(self, text: str) -> list[float]:
        self._load()
        vec = await asyncio.to_thread(self._model.encode, text)
        return vec.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Native batch encoding — more efficient than concurrent single embeds."""
        if not texts:
            return []
        self._load()
        def _encode():
            return self._model.encode(texts).tolist()
        return await asyncio.to_thread(_encode)
