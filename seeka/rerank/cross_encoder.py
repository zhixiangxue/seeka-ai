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
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise ImportError(
                    "Local cross-encoder rerank requires the optional "
                    "`sentence-transformers` dependency. Install it with:\n"
                    "    pip install 'seeka[local-embed]'\n"
                    "(adds ~5 GB; or use a cloud reranker via `rerank_uri`, "
                    "e.g. 'cohere/rerank-english-v3.0' or 'bailian/gte-rerank')."
                ) from e
            self._model = CrossEncoder(self._model_name)

    async def rerank(self, query: str, docs: list[str]) -> list[int]:
        self._load()
        pairs = [(query, doc) for doc in docs]
        scores = await asyncio.to_thread(self._model.predict, pairs)
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
