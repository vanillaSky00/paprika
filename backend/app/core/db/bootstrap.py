from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.exceptions import DatabaseUnavailableError, PgvectorExtensionError


async def ping_database(engine: AsyncEngine) -> None:
    """Verify that the configured database accepts a simple query."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise DatabaseUnavailableError(
            f"Database connectivity probe failed: {exc}"
        ) from exc


async def ensure_pgvector_extension(engine: AsyncEngine) -> None:
    """Install pgvector support before migrations create vector columns."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except SQLAlchemyError as exc:
        raise PgvectorExtensionError(
            f"Could not ensure pgvector extension: {exc}"
        ) from exc
