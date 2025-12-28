import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from alembic.config import Config
from alembic import command

logger = logging.getLogger(__name__)

def _run_migrations():
    """Private helper to run DB migrations internally."""
    try:
        logger.info("🔄 Checking Database Schema...")
        # Point to your alembic.ini (usually in root)
        alembic_cfg = Config("alembic.ini")
        # Run 'alembic upgrade head'
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Database is ready!")
    except Exception as e:
        logger.error(f"❌ Database migration failed: {e}")
        # In dev, we might want to crash. In prod, maybe retry.
        raise e

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    _run_migrations()
    
    # You can also preload things here
    # from app.deps import get_llm
    # get_llm() # Warm up the cache
    
    yield
    
    # --- SHUTDOWN ---
    # await db.disconnect() if needed
    logger.info("🛑 Shutting down Paprika Backend...")