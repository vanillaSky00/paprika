from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.api.schemas import CreateMemoryDTO, MemoryDTO, SkillDTO
from app.core.db.repository import Repository
from app.memory.base import BaseMemoryStore
from app.memory.models import Memory, Skill
from app.llm.embeddings import embed_text


class PostgresMemoryStore(BaseMemoryStore):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def save(self, memory: CreateMemoryDTO) -> None:
        async with self._session_factory() as db:
            emb = embed_text(memory.content)

            db_mem = Memory(
                in_game_day=memory.day,
                time_slot=memory.time,
                mode=memory.mode,
                location_id=memory.location_id,
                memory_type=memory.memory_type,
                content=memory.content,
                emotion_tags=memory.emotion_tags,
                importance=memory.importance,
                embedding=emb,
            )
            await Repository(db, Memory).add(db_mem)

            await db.commit()

    async def fetch_recent(
        self, *, day: int, limit: int = 20, actor_id: int | None = None
    ) -> List[MemoryDTO]:
        async with self._session_factory() as db:
            stmt = (
                select(Memory)
                .filter(Memory.in_game_day <= day)
                .order_by(Memory.in_game_day.desc(), Memory.time_slot.desc())
                .limit(limit)
            )
            if actor_id is not None:
                stmt = stmt.where(Memory.actor_id == actor_id)
            result = await db.execute(stmt)
            rows = result.scalars().all()

            return [MemoryDTO.model_validate(row) for row in rows]

    async def fetch_similar(
        self, *, query: str, limit: int = 10, actor_id: int | None = None
    ) -> List[MemoryDTO]:
        async with self._session_factory() as db:
            q_emb = embed_text(query)
            stmt = (
                select(Memory)
                .order_by(Memory.embedding.l2_distance(q_emb))
                .limit(limit)
            )
            if actor_id is not None:
                stmt = stmt.where(Memory.actor_id == actor_id)
            result = await db.execute(stmt)
            rows = result.scalars().all()

            return [MemoryDTO.model_validate(row) for row in rows]

    async def fetch_similar_skills(
        self, *, query: str, limit: int = 3, actor_id: int | None = None
    ) -> List[SkillDTO]:
        async with self._session_factory() as db:
            q_emb = embed_text(query)
            stmt = (
                select(Skill)
                .order_by(Skill.embedding.l2_distance(q_emb))
                .limit(limit)
            )
            if actor_id is not None:
                stmt = stmt.where(Skill.actor_id == actor_id)
            result = await db.execute(stmt)
            rows = result.scalars().all()

            return [SkillDTO.model_validate(row) for row in rows]

    async def save_skill(
        self, skill: SkillDTO, *, actor_id: int | None = None
    ) -> None:
        """
        Update if exist, otherwise save. The (actor_id, task_name) pair
        is the unique key per ADR-011; when `actor_id` is None the lookup
        falls back to task_name-only for legacy callers.
        """
        async with self._session_factory() as db:
            stmt = select(Skill).where(Skill.task_name == skill.task_name)
            if actor_id is not None:
                stmt = stmt.where(Skill.actor_id == actor_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()

            emb = embed_text(f"{skill.task_name}: {skill.description}")

            if existing:
                existing.steps_text = skill.steps_text
                existing.embedding = emb
                existing.updated_at = func.now()

            else:
                new_skill = Skill(
                    task_name = skill.task_name,
                    description = skill.description,
                    steps_text = skill.steps_text,
                    embedding = emb
                )
                await Repository(db, Skill).add(new_skill)

            await db.commit()
