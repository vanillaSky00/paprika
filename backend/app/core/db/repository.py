from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

ModelT = TypeVar("ModelT")


class Repository(Generic[ModelT]):
    """Small SQLAlchemy CRUD helper for model-level persistence.

    Domain repositories can compose this for boring create/read/delete work and
    keep their own files focused on domain queries and behavior.
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self.session = session
        self.model = model

    async def get(self, entity_id: Any) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        statement: Select[tuple[ModelT]] | None = None,
    ) -> Sequence[ModelT]:
        stmt = statement if statement is not None else select(self.model)
        result = await self.session.execute(stmt.offset(offset).limit(limit))
        return result.scalars().all()

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        return await self.add(instance)

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
