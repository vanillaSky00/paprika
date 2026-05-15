from abc import ABC, abstractmethod
from typing import List

from app.api.schemas import CreateMemoryDTO, MemoryDTO, SkillDTO


class BaseMemoryStore(ABC):
    @abstractmethod
    async def save(self, memory: CreateMemoryDTO) -> None:
        pass

    @abstractmethod
    async def fetch_recent(
        self, *, day: int, limit: int = 20, actor_id: int | None = None
    ) -> List[MemoryDTO]:
        pass

    @abstractmethod
    async def fetch_similar(
        self, *, query: str, limit: int = 10, actor_id: int | None = None
    ) -> List[MemoryDTO]:
        pass

    @abstractmethod
    async def fetch_similar_skills(
        self, *, query: str, limit: int = 3, actor_id: int | None = None
    ) -> List[SkillDTO]:
        pass

    @abstractmethod
    async def save_skill(
        self, skill: SkillDTO, *, actor_id: int | None = None
    ) -> None:
        pass
