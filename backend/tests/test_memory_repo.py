import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import your actual code
from app.memory.models import Base, Memory
from app.memory.pgvector_repo import PostgresMemoryStore
from app.api.schemas import CreateMemoryDTO, MemoryDTO

# Use the same DB URL from your .env or Docker
TEST_DATABASE_URL = "postgresql+asyncpg://admin:password@localhost:5432/paprika_ai"

# --- FIXTURES (Setup & Teardown) ---

@pytest_asyncio.fixture
async def db_session():
    """
    Creates a fresh database session for a test, 
    and rolls back changes at the end so tests don't mess each other up.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # 1. Create Tables (if they don't exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Return a Session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session  # Pass session to the test function
        
        # 3. Cleanup: Delete all memories after test
        await session.execute("TRUNCATE TABLE memories RESTART IDENTITY")
        await session.commit()
    
    await engine.dispose()

@pytest.fixture
def memory_store(db_session):
    """
    Returns an instance of your Repo, but bypasses the session_factory 
    logic to use our active test session.
    """
    # We create a fake factory that just yields our open test session
    # This is a common trick to inject the test transaction
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_factory():
        yield db_session

    return PostgresMemoryStore(mock_factory)


# --- TESTS ---

@pytest.mark.asyncio
async def test_save_and_fetch_recent(memory_store):
    """Test that we can save a memory and read it back."""
    
    # 1. Create a dummy memory
    new_mem = CreateMemoryDTO(
        day=1,
        time=8,
        mode="reality",
        location="bedroom",
        memory_type="observation",
        content="I woke up feeling cold.",
        emotion_tags=["cold", "neutral"],
        importance=0.3
    )

    # 2. Save it
    await memory_store.save(new_mem)

    # 3. Fetch it back
    recent = await memory_store.fetch_recent(day=1, limit=5)

    assert len(recent) == 1
    assert recent[0].content == "I woke up feeling cold."
    assert recent[0].location == "bedroom"
    assert recent[0].emotion_tags == ["cold", "neutral"]

@pytest.mark.asyncio
async def test_vector_search(memory_store):
    """Test that vector search returns relevant results."""
    
    # 1. Insert two distinct memories
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

    # 2. Search for something scary (should match mem2)
    # Note: Since we are using real embeddings, 'eye' and 'watching' should match closer than 'coffee'
    results = await memory_store.fetch_similar(query="giant eye sky", limit=1)

    assert len(results) > 0
    assert results[0].content == "A giant eye is watching me from the sky."