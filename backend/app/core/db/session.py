from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
)

_session_factory = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_engine() -> AsyncEngine:
    """Return the application-wide async SQLAlchemy engine."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the application-wide async session factory."""
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields one async DB session."""
    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a session and rollback on errors.

    Repositories decide when to commit. This helper only makes failure behavior
    consistent for service code that wants a scoped session.
    """
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Dispose pooled database connections during application shutdown."""
    await _engine.dispose()
    logger.info("Database connections closed.")
