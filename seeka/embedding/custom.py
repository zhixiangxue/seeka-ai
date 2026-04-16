from typing import Callable
from .base import EmbeddingBase


class CustomEmbedding(EmbeddingBase):
    """
    Wrap a user-supplied fn: str -> list[float].
    """

    def __init__(self, fn: Callable[[str], list[float]]):
        self._fn = fn

    def embed(self, text: str) -> list[float]:
        return self._fn(text)
