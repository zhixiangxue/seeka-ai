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
