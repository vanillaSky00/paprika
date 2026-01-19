import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock
from app.llm.base import BaseLLMClient
from app.agents.curriculum import CurriculumAgent
from app.memory.base import BaseMemoryStore
from app.api.schemas import CurriculumOutput, MemoryDTO
from app.config import settings
from app.deps import get_default_llm

@pytest.fixture
def mock_dependencies():
    mock_qa = MagicMock(spec=BaseLLMClient)
    mock_memory = MagicMock(spec=BaseMemoryStore)
    mock_memory.fetch_similar = AsyncMock(return_value=[
        MemoryDTO(
            id=1, in_game_day=1, time_slot=10, mode="reality", location_id="Kitchen", 
            memory_type="fact", content="The stove is hot.", emotion_tags=[], importance=5.0, embedding=[], created_at=datetime.now()
        )
    ])
    return mock_qa, mock_memory

def test_curriculum_prompt_rendering(dummy_perception, mock_dependencies):
    mock_llm = MagicMock(spec=BaseLLMClient)
    mock_qa, mock_memory = mock_dependencies
    
    agent = CurriculumAgent(
        llm=mock_llm, 
        qa_llm=mock_qa, 
        memory_store=mock_memory,
        mode="auto"
    )
    
    agent.recent_history = [
        {"task": "Open Fridge", "result": "success"},
        {"task": "Grab Tomato", "result": "success"},
    ]

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

    assert "Kitchen_A" in human_msg.content 
    assert "The stove is hot" in human_msg.content
    assert "Grab Tomato" in human_msg.content

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.LLM_API_KEY,
    reason="LLM_API_KEY not set; skipping live OpenAI test.",
)
async def test_curriculum_integration_live(dummy_perception, mock_dependencies):
    llm = get_default_llm()
    mock_qa, mock_memory = mock_dependencies
    
    agent = CurriculumAgent(
        llm=llm, 
        qa_llm=mock_qa, 
        memory_store=mock_memory,
        mode="auto"
    )

    # FIX: Use nested 'self.held_item'
    dummy_perception.self.held_item = None
    
    result = await agent.propose_next_task(perception=dummy_perception)

    print(f"\n[Curriculum Output]: {result}")

    assert isinstance(result, CurriculumOutput)
    assert isinstance(result.task, str)
    assert len(result.task) > 0
    assert "cook" not in result.task.lower()