from typing import Callable
from .base import RerankBase


class CustomRerank(RerankBase):
    """
    Wrap a user-supplied fn: (query: str, docs: list[str]) -> list[int].
    """

    def __init__(self, fn: Callable[[str, list[str]], list[int]]):
        self._fn = fn

    def rerank(self, query: str, docs: list[str]) -> list[int]:
        return self._fn(query, docs)
