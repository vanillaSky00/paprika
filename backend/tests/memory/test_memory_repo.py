# patch lets you temporarily replace a function or object during tests.
from unittest.mock import patch

import pytest
import pytest_asyncio

# text() lets you execute raw SQL (e.g., CREATE EXTENSION vector).
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.schemas import CreateMemoryDTO
from app.memory.models import Base
from app.memory.pgvector_repo import PostgresMemoryStore

TEST_DATABASE_URL = "postgresql+asyncpg://admin:password@localhost:5432/paprika_ai"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.execute(text("TRUNCATE TABLE memories RESTART IDENTITY"))
        await session.commit()
    await engine.dispose()


@pytest.fixture
def memory_store(db_session):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_factory():
        yield db_session

    return PostgresMemoryStore(mock_factory)


@pytest.mark.asyncio
async def test_save_and_fetch_recent(memory_store):
    # We patch the 'embed_text' function inside the repo module
    # We allow it to return a fake list of 1536 floats (OpenAI size)
    with patch("app.memory.pgvector_repo.embed_text") as mock_embed:
        mock_embed.return_value = [0.1] * 1536

        new_mem = CreateMemoryDTO(
            day=1,
            time=8,
            mode="reality",
            location_id="bedroom",
            memory_type="observation",
            content="I woke up feeling cold.",
            emotion_tags=["cold", "neutral"],
            importance=0.3,
        )
        await memory_store.save(new_mem)

        recent = await memory_store.fetch_recent(day=1, limit=5)
        assert len(recent) == 1
        assert recent[0].content == "I woke up feeling cold."


@pytest.mark.asyncio
async def test_vector_search(memory_store):
    with patch("app.memory.pgvector_repo.embed_text") as mock_embed:
        # Mocking returns consistent vectors so we can test logic without API calls
        mock_embed.return_value = [0.1] * 1536

        mem1 = CreateMemoryDTO(
            day=1,
            time=10,
            mode="reality",
            location_id="kitchen",
            memory_type="obs",
            content="The coffee smells burnt.",
            importance=0.1,
        )
        mem2 = CreateMemoryDTO(
            day=1,
            time=12,
            mode="dream",
            location_id="void",
            memory_type="dream",
            content="A giant eye is watching me from the sky.",
            importance=0.9,
        )

        await memory_store.save(mem1)
        await memory_store.save(mem2)

        results = await memory_store.fetch_similar(query="giant eye sky", limit=1)
        assert len(results) > 0
