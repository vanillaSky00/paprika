from abc import ABC, abstractmethod
from typing import List

from app.api.schemas import CreateMemoryDTO, MemoryDTO


class BaseMemoryStore(ABC):
    @abstractmethod
    async def save(self, memory: CreateMemoryDTO) -> None:  # Added 'async'
        pass

    @abstractmethod
    async def fetch_recent(
        self, *, day: int, limit: int = 20
    ) -> List[MemoryDTO]:  # Added 'async'
        pass

    @abstractmethod
    async def fetch_similar(
        self, *, query: str, limit: int = 10
    ) -> List[MemoryDTO]:  # Added 'async'
        pass
