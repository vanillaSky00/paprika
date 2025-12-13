import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from app.llm.base import BaseLLMClient
from app.agents.curriculum import CurriculumAgent
from app.memory.base import BaseMemoryStore
from app.api.schemas import CurriculumOutput, MemoryDTO
from app.config import settings
from app.deps import get_default_llm

# --- FIXTURES ---
@pytest.fixture
def mock_dependencies():
    """
    Creates mocks for the complex dependencies (Memory, QA LLM)
    so we can test the Curriculum logic in isolation.
    """
    # 1. Mock QA LLM
    mock_qa = MagicMock(spec=BaseLLMClient)
    
    # 2. Mock Memory Store (Must be Async!)
    mock_memory = MagicMock(spec=BaseMemoryStore)
    mock_memory.fetch_similar = AsyncMock(return_value=[
        MemoryDTO(
            id=1, in_game_day=1, time_slot=10, mode="reality", location_id="Kitchen", 
            memory_type="fact", content="The stove is hot.", emotion_tags=[], importance=5.0, embedding=[], created_at=datetime.now()
        )
    ])
    
    return mock_qa, mock_memory

# --- TEST 1: PROMPT RENDERING (Fast, No Cost) ---
def test_curriculum_prompt_rendering(dummy_perception, mock_dependencies):
    """
    Verifies that the Agent correctly builds the prompt using Perception + Memories.
    """
    mock_llm = MagicMock(spec=BaseLLMClient)
    mock_qa, mock_memory = mock_dependencies
    
    # Init Agent with Mocks
    agent = CurriculumAgent(
        llm=mock_llm, 
        qa_llm=mock_qa, 
        memory_store=mock_memory,
        mode="auto"
    )

    # Inject fake history
    agent.recent_tasks = ["Open Fridge", "Grab Tomato"]

    # Render
    # We pass a fake list of memories to simulate what 'fetch_similar' would return
    fake_memories = [
        MemoryDTO(
            id=1, in_game_day=1, time_slot=10, mode="reality", location_id="Kitchen", 
            memory_type="fact", content="The stove is hot.", emotion_tags=[], importance=5.0, embedding=[], created_at=datetime.now()
        )
    ]
    
    human_msg = agent.render_human_message(
        perception=dummy_perception, 
        long_term_memories=fake_memories
    )

    print(f"\n[Curriculum Prompt]:\n{human_msg.content}")

    # Assertions
    assert human_msg is not None
    assert "Kitchen_A" in human_msg.content  # From Perception
    assert "The stove is hot" in human_msg.content # From Memory
    assert "Grab Tomato" in human_msg.content # From Recent History
    assert "--- RELEVANT MEMORIES" in human_msg.content


# --- TEST 2: LIVE LLM INTEGRATION (Paid, Real Logic) ---
@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_curriculum_integration_live(dummy_perception, mock_dependencies):
    """
    Scenario: Agent is in the Kitchen holding nothing.
    Expected: Agent should propose a task to find/explore items (e.g., "Open Fridge").
    """
    llm = get_default_llm() # Real LLM
    mock_qa, mock_memory = mock_dependencies
    
    agent = CurriculumAgent(
        llm=llm, 
        qa_llm=mock_qa, 
        memory_store=mock_memory,
        mode="auto"
    )

    # Setup State: Holding Nothing, sees a Fridge
    dummy_perception.held_item = None
    
    # Run Agent
    # Note: This will call the REAL LLM, but the MOCKED Memory
    result = await agent.propose_next_task(perception=dummy_perception)

    print(f"\n[Curriculum Output]: {result}")

    # Assertions
    assert isinstance(result, CurriculumOutput)
    assert isinstance(result.task, str)
    assert len(result.task) > 0
    assert isinstance(result.difficulty, int)
    
    # Logic Check: Since we are holding nothing, it shouldn't ask us to cook yet
    assert "cook" not in result.task.lower()