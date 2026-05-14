import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI

from alembic import command
from app.core.config import settings
from app.core.db import close_db, get_engine
from app.core.db.bootstrap import ensure_pgvector_extension, ping_database
from app.core.exceptions import MigrationError
from app.core.logger import setup_logging

logger = logging.getLogger(__name__)


ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _run_migrations():
    """
    Synchronous wrapper for Alembic.
    This MUST run in a separate thread to allow asyncio.run() inside env.py.
    """
    try:
        logger.info("Checking database schema...")
        alembic_cfg = Config(str(ALEMBIC_INI))
        command.upgrade(alembic_cfg, "head")
        logger.info("Database schema is ready.")
    except Exception as exc:
        logger.error("Database migration failed: %s", exc)
        raise MigrationError(f"Alembic upgrade failed: {exc}") from exc


async def _init_database() -> None:
    engine = get_engine()
    await ping_database(engine)
    await ensure_pgvector_extension(engine)
    await asyncio.to_thread(_run_migrations)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    await _init_database()

    try:
        yield
    finally:
        logger.info("Shutting down Paprika Backend...")
        await close_db()
