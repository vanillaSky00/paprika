from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.schemas import CreateMemoryDTO, MemoryDTO, SkillDTO
from app.llm.embeddings import embed_text
from app.memory.memory_repo import EpisodeMemoryRepo, MessageRepo, SkillRepo
from app.memory.models import Memory, Message, Skill


class AsyncMemoryManager:
    """
    Service layer over the memory repos.
    Owns the transaction boundary and embedding generation; orchestrates work
    that spans more than one aggregate. Agents call this — not the repos.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    # Episode memory
    async def record_observation(
        self,
        memory_in: CreateMemoryDTO,
        *,
        actor_id: int,
    ) -> MemoryDTO:
        emb = embed_text(memory_in.content)
        async with self._session_factory() as session:
            row = Memory(
                actor_id=actor_id,
                in_game_day=memory_in.day,
                time_slot=memory_in.time,
                mode=memory_in.mode,
                location_id=memory_in.location_id,
                memory_type=memory_in.memory_type,
                content=memory_in.content,
                emotion_tags=memory_in.emotion_tags,
                importance=memory_in.importance,
                embedding=emb,
            )
            await EpisodeMemoryRepo(session).add(row)
            await session.commit()
            await session.refresh(row)
            return MemoryDTO.model_validate(row)

    async def recall_similar_memories(
        self,
        *,
        query: str,
        limit: int = 10,
        actor_id: int | None = None,
    ) -> list[MemoryDTO]:
        emb = embed_text(query)
        async with self._session_factory() as session:
            rows = await EpisodeMemoryRepo(session).fetch_similar(
                embedding=emb, limit=limit, actor_id=actor_id
            )
            return [MemoryDTO.model_validate(r) for r in rows]

    async def recall_recent_memories(
        self,
        *,
        actor_id: int,
        day: int,
        limit: int = 20,
    ) -> list[MemoryDTO]:
        async with self._session_factory() as session:
            rows = await EpisodeMemoryRepo(session).fetch_recent_for_day(
                actor_id=actor_id, day=day, limit=limit
            )
            return [MemoryDTO.model_validate(r) for r in rows]

    # Skills 
    async def learn_skill(
        self,
        skill: SkillDTO,
        *,
        actor_id: int,
    ) -> None:
        emb = embed_text(f"{skill.task_name}: {skill.description}")
        async with self._session_factory() as session:
            repo = SkillRepo(session)
            existing = await repo.find_by_task_name(
                actor_id=actor_id, task_name=skill.task_name
            )
            if existing is not None:
                existing.description = skill.description
                existing.steps_text = skill.steps_text
                existing.embedding = emb
                existing.updated_at = func.now()
            else:
                await repo.add(
                    Skill(
                        actor_id=actor_id,
                        task_name=skill.task_name,
                        description=skill.description,
                        steps_text=skill.steps_text,
                        embedding=emb,
                    )
                )
            await session.commit()

    async def recall_similar_skills(
        self,
        *,
        query: str,
        limit: int = 3,
        actor_id: int | None = None,
    ) -> list[SkillDTO]:
        emb = embed_text(query)
        async with self._session_factory() as session:
            rows = await SkillRepo(session).fetch_similar(
                embedding=emb, limit=limit, actor_id=actor_id
            )
            return [SkillDTO.model_validate(r) for r in rows]

    # Cross-aggregate orchestration 
    async def recall_for_task(
        self,
        *,
        query: str,
        memory_limit: int = 10,
        skill_limit: int = 3,
        actor_id: int | None = None,
    ) -> tuple[list[MemoryDTO], list[SkillDTO]]:
        # One embed, one session — the payoff for having a manager.
        emb = embed_text(query)
        async with self._session_factory() as session:
            mem_rows = await EpisodeMemoryRepo(session).fetch_similar(
                embedding=emb, limit=memory_limit, actor_id=actor_id
            )
            skill_rows = await SkillRepo(session).fetch_similar(
                embedding=emb, limit=skill_limit, actor_id=actor_id
            )
            return (
                [MemoryDTO.model_validate(r) for r in mem_rows],
                [SkillDTO.model_validate(r) for r in skill_rows],
            )

    # Messages 
    async def post_message(
        self,
        *,
        from_actor_id: int,
        to_actor_id: int | None,
        content: str,
        channel: str = "global",
    ) -> None:
        async with self._session_factory() as session:
            await MessageRepo(session).add(
                Message(
                    from_actor_id=from_actor_id,
                    to_actor_id=to_actor_id,
                    channel=channel,
                    content=content,
                )
            )
            await session.commit()