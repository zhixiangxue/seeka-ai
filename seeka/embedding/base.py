from abc import ABC, abstractmethod
import asyncio


class EmbeddingBase(ABC):

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Default: concurrent single embeds."""
        if not texts:
            return []
        return list(await asyncio.gather(*[self.embed(t) for t in texts]))
