from typing import List

from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.schemas import CreateMemoryDTO, MemoryDTO, SkillDTO
from app.memory.base import BaseMemoryStore
from app.memory.models import Memory, Skill
from app.memory.vector_store import embed_text


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
            db.add(db_mem)

            await db.commit()

    async def fetch_recent(self, *, day: int, limit: int = 20) -> List[MemoryDTO]:
        async with self._session_factory() as db:
            stmt = (
                select(Memory)
                .filter(Memory.in_game_day <= day)
                .order_by(Memory.in_game_day.desc(), Memory.time_slot.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

            return [MemoryDTO.model_validate(row) for row in rows]

    async def fetch_similar(self, *, query: str, limit: int = 10) -> List[MemoryDTO]:
        async with self._session_factory() as db:
            q_emb = embed_text(query)
            stmt = (
                select(Memory)
                .order_by(Memory.embedding.l2_distance(q_emb))
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()

            return [MemoryDTO.model_validate(row) for row in rows]
        
    async def fetch_similar_skills(self, *, query: str, limit: int = 3) -> List[SkillDTO]:
        async with self._session_factory() as db:
            q_emb = embed_text(query)
            stmt = (
                select(Skill)
                .order_by(Skill.embedding.l2_distance(q_emb))
                .limit(limit)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            
            return [SkillDTO.model_validate(row) for row in rows]

    async def save_skill(self, skill: SkillDTO) -> None:
        """
        Update if exist, otherwise save
        """
        async with self._session_factory() as db:
            stmt = select(Skill).where(Skill.task_name == skill.task_name)
            existing = (await db.execute(stmt)).scalar_one_or_none()
            
            emb = embed_text(f"{skill.task_name}: {skill.description}")

            if existing:
                existing.step_text = skill.steps_text
                existing.embedding = emb
                existing.updated_at = func.now()
                
            else:
                new_skill = Skill(
                    task_name = skill.task_name,
                    description = skill.description,
                    step_text = skill.steps_text,
                    embedding = emb
                )
                db.add(new_skill)

            await db.commit()
