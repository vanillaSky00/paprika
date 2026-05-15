from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.repository import Repository
from app.memory.models import Memory, Message, Skill


class EpisodeMemoryRepo(Repository[Memory]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Memory)

    async def fetch_recent_for_day(
        self,
        *,
        actor_id: int,
        day: int,
        limit: int = 20,
    ) -> Sequence[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.actor_id == actor_id, Memory.in_game_day <= day)
            .order_by(Memory.in_game_day.desc(), Memory.time_slot.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def fetch_similar(
        self,
        *,
        embedding: list[float],
        limit: int = 10,
        actor_id: int | None = None,
    ) -> Sequence[Memory]:
        stmt = select(Memory).order_by(Memory.embedding.l2_distance(embedding)).limit(limit)
        if actor_id is not None:
            stmt = stmt.where(Memory.actor_id == actor_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SkillRepo(Repository[Skill]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Skill)

    async def find_by_task_name(
        self,
        *,
        actor_id: int,
        task_name: str,
    ) -> Skill | None:
        stmt = select(Skill).where(
            Skill.actor_id == actor_id,
            Skill.task_name == task_name,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def fetch_similar(
        self,
        *,
        embedding: list[float],
        limit: int = 3,
        actor_id: int | None = None,
    ) -> Sequence[Skill]:
        stmt = select(Skill).order_by(Skill.embedding.l2_distance(embedding)).limit(limit)
        if actor_id is not None:
            stmt = stmt.where(Skill.actor_id == actor_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class MessageRepo(Repository[Message]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)

    async def fetch_recent_for_channel(
        self,
        *,
        channel: str,
        limit: int = 50,
    ) -> Sequence[Message]:
        stmt = (
            select(Message)
            .where(Message.channel == channel)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
