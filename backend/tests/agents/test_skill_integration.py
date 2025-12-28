import pytest
from unittest.mock import MagicMock, AsyncMock
from app.llm.base import BaseLLMClient
from app.agents.skill import SkillAgent
from app.memory.base import BaseMemoryStore
from app.api.schemas import SkillDTO
from app.config import settings
from app.deps import get_default_llm

# Define skip logic
should_skip_live = (
    not settings.OPENAI_API_KEY or 
    str(settings.OPENAI_API_KEY).startswith("dummy")
)

@pytest.fixture
def mock_dependencies():
    """
    Creates mocks for LLM and MemoryStore to test logic in isolation.
    """
    mock_llm = MagicMock(spec=BaseLLMClient)
    mock_memory = MagicMock(spec=BaseMemoryStore)
    
    # Setup default return for fetch_similar_skills
    mock_memory.fetch_similar_skills = AsyncMock(return_value=[])
    # Setup default return for save_skill
    mock_memory.save_skill = AsyncMock(return_value=True)
    
    return mock_llm, mock_memory


def test_skill_prompt_rendering(mock_dependencies):
    """
    Verifies that the Agent correctly formats the Raw History into a Human Message.
    """
    mock_llm, mock_memory = mock_dependencies
    agent = SkillAgent(llm=mock_llm, memory_store=mock_memory)

    # Input Data
    task = "Make a Coffee"
    history = [
        {"action": "MoveTo", "target": "Kitchen_Counter_05"},
        {"action": "Interact", "target": "Coffee_Machine_01"},
        {"action": "Wait", "duration": 5}
    ]

    # Render
    human_msg = agent.render_human_message(task=task, action_history=history)

    print(f"\n[Skill Prompt]:\n{human_msg.content}")

    # Assertions
    assert human_msg is not None
    assert "Make a Coffee" in human_msg.content
    assert "Coffee_Machine_01" in human_msg.content
    assert "Standard Operating Procedure" in human_msg.content


@pytest.mark.asyncio
async def test_skill_learning_logic(mock_dependencies):
    """
    Verifies that learn_new_skill calls the LLM and saves to Memory.
    """
    mock_llm, mock_memory = mock_dependencies
    
    # Mock LLM to return a valid JSON SkillDTO
    mock_llm.generate_response = AsyncMock(return_value="""
    {
        "task_name": "Cook Steamed Fish",
        "description": "A guide to cooking fish using the steamer.",
        "steps_text": "1. Go to Fridge.\\n2. Grab Fish.\\n3. Put in Steamer."
    }
    """)
    
    agent = SkillAgent(llm=mock_llm, memory_store=mock_memory)

    # Input: Raw, messy actions
    task_name = "Cook Steamed Fish"
    raw_history = [
        {"action": "Move", "coord": {"x": 12.5, "y": 0, "z": 5}},
        {"action": "Interact", "target": "Fridge_02"},
        {"action": "Grab", "item": "Raw_Fish_ID_99"},
    ]

    # Run Learn
    # Note: We pass success=True so it actually triggers
    await agent.learn_new_skill(
        task=task_name, 
        action_history=raw_history, 
        success=True
    )

    # Assertions
    # 1. Verify save_skill was called on the memory store
    assert mock_memory.save_skill.called, "Agent did not try to save the skill!"
    
    # 2. Verify the data passed to save_skill was correct
    # args[0] is the first argument passed to save_skill
    saved_skill = mock_memory.save_skill.call_args.args[0]
    assert isinstance(saved_skill, SkillDTO)
    assert saved_skill.task_name == "Cook Steamed Fish"
    assert "Go to Fridge" in saved_skill.steps_text


@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    should_skip_live,
    reason="OPENAI_API_KEY missing or dummy; skipping live test.",
)
async def test_skill_integration_live():
    """
    LIVE TEST: Checks if the LLM can actually summarize raw logs into a Skill.
    """
    llm = get_default_llm()
    # We still mock memory because we don't want to write to real DB in this test
    mock_memory = MagicMock(spec=BaseMemoryStore)
    mock_memory.save_skill = AsyncMock(return_value=True)
    
    agent = SkillAgent(llm=llm, memory_store=mock_memory)
    
    task_name = "Toast Bread"
    raw_history = [
        {"function": "move_to", "args": {"target": "Fridge"}},
        {"function": "pickup", "args": {"item": "Bread"}},
        {"function": "move_to", "args": {"target": "Toaster"}},
        {"function": "interact", "args": {"action": "on"}}
    ]
    
    await agent.learn_new_skill(
        task=task_name,
        action_history=raw_history,
        success=True
    )
    
    assert mock_memory.save_skill.called
    saved_skill = mock_memory.save_skill.call_args.args[0]
    
    print(f"\n[Live Skill Learned]:\n{saved_skill.steps_text}")
    assert len(saved_skill.steps_text) > 10