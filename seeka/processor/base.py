from abc import ABC, abstractmethod

from ..models import Memo


class ProcessorBase(ABC):

    @abstractmethod
    async def process(self, content: str) -> list[Memo]:
        """
        Accept raw content and return a list of Memo objects to be stored.
        Only the content field needs to be filled; id and namespace are assigned later.
        """
        ...
