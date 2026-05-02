# app/lifecycle.py
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from alembic.config import Config
from alembic import command
from app.core.config import settings
from app.core.logger import setup_logging

logger = logging.getLogger(__name__)

def _run_migrations():
    """
    Synchronous wrapper for Alembic.
    This MUST run in a separate thread to allow asyncio.run() inside env.py.
    """
    try:
        logger.info("🔄 Checking Database Schema...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Database is ready!")
    except Exception as e:
        logger.error(f"❌ Database migration failed: {e}")
        raise e

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings)
    await asyncio.to_thread(_run_migrations)
    
    yield
    
    logger.info("🛑 Shutting down Paprika Backend...")