from .base import EmbeddingBase


class LocalEmbedding(EmbeddingBase):
    """
    Default local embedding. Lazily loads all-MiniLM-L6-v2 (384-dim, ~80MB, no external deps).
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.MODEL_NAME)

    def embed(self, text: str) -> list[float]:
        self._load()
        return self._model.encode(text).tolist()
