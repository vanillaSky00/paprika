# app/lifecycle.py
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from alembic.config import Config
from alembic import command

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
    # --- STARTUP ---
    
    # ✅ FIX: Run the blocking sync function in a separate thread
    # This prevents "asyncio.run() cannot be called from a running event loop"
    await asyncio.to_thread(_run_migrations)
    
    yield
    
    # --- SHUTDOWN ---
    logger.info("🛑 Shutting down Paprika Backend...")