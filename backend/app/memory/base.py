# paprika_agent_backend/memory/base.py
from abc import ABC, abstractmethod
from typing import List
from ..api.schemas import MemoryDTO, CreateMemoryDTO

class BaseMemoryStore(ABC):
    @abstractmethod
    def save(self, memory: CreateMemoryDTO) -> None:
        pass

    @abstractmethod
    def fetch_recent(self, *, day: int, limit: int = 20) -> List[MemoryDTO]:
        pass

    @abstractmethod
    def fetch_similar(self, *, query: str, limit: int = 10) -> List[MemoryDTO]:
        pass