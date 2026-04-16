from .base import RerankBase


class LocalRerank(RerankBase):
    """
    Local rerank implementation using a cross-encoder.
    Lazily loads cross-encoder/ms-marco-MiniLM-L-6-v2.
    """

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = None):
        self._model_name = model_name or self.MODEL_NAME
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self._model_name)

    def rerank(self, query: str, docs: list[str]) -> list[int]:
        self._load()
        pairs = [(query, doc) for doc in docs]
        scores = self._model.predict(pairs)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return ranked
