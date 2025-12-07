import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text  # <--- NEW IMPORT

# Import your actual code
from app.memory.models import Base
from app.memory.pgvector_repo import PostgresMemoryStore
from app.api.schemas import CreateMemoryDTO

# Use the same DB URL from your .env or Docker
TEST_DATABASE_URL = "postgresql+asyncpg://admin:password@localhost:5432/paprika_ai"

# --- FIXTURES (Setup & Teardown) ---

@pytest_asyncio.fixture
async def db_session():
    """
    Creates a fresh database session for a test, 
    and rolls back changes at the end.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # 1. Setup DB (Enable Vector & Create Tables)
    async with engine.begin() as conn:
        # FIX: Enable the extension BEFORE creating tables
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # 2. Return a Session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
        
        # 3. Cleanup: Delete all memories after test
        await session.execute(text("TRUNCATE TABLE memories RESTART IDENTITY"))
        await session.commit()
    
    await engine.dispose()

@pytest.fixture
def memory_store(db_session):
    """
    Returns an instance of your Repo using the active test session.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_factory():
        yield db_session

    return PostgresMemoryStore(mock_factory)

# --- TESTS (No changes needed below) ---

@pytest.mark.asyncio
async def test_save_and_fetch_recent(memory_store):
    new_mem = CreateMemoryDTO(
        day=1, time=8, mode="reality", location="bedroom", memory_type="observation",
        content="I woke up feeling cold.", emotion_tags=["cold", "neutral"], importance=0.3
    )
    await memory_store.save(new_mem)
    recent = await memory_store.fetch_recent(day=1, limit=5)

    assert len(recent) == 1
    assert recent[0].content == "I woke up feeling cold."

@pytest.mark.asyncio
async def test_vector_search(memory_store):
    mem1 = CreateMemoryDTO(
        day=1, time=10, mode="reality", location="kitchen", memory_type="obs",
        content="The coffee smells burnt.", importance=0.1
    )
    mem2 = CreateMemoryDTO(
        day=1, time=12, mode="dream", location="void", memory_type="dream",
        content="A giant eye is watching me from the sky.", importance=0.9
    )
    
    await memory_store.save(mem1)
    await memory_store.save(mem2)

    # Note: This will use the real OpenAI API if OPENAI_API_KEY is set,
    # or fail if not. For unit tests, usually we mock the embedding function,
    # but for this integration test, ensure the key is in GitHub Secrets.
    results = await memory_store.fetch_similar(query="giant eye sky", limit=1)

    assert len(results) > 0
    assert results[0].content == "A giant eye is watching me from the sky."