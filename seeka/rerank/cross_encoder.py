import asyncio

from .base import RerankBase


class CrossEncoderRerank(RerankBase):
    """
    In-process rerank via sentence-transformers CrossEncoder.
    Lazily loads cross-encoder/ms-marco-MiniLM-L-6-v2. Zero config, no external server.
    """

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = None):
        self._model_name = model_name or self.MODEL_NAME
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)

    async def rerank(self, query: str, docs: list[str]) -> list[int]:
        self._load()
        pairs = [(query, doc) for doc in docs]
        scores = await asyncio.to_thread(self._model.predict, pairs)
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
