import pytest
from unittest.mock import MagicMock, AsyncMock
from app.llm.base import BaseLLMClient
from app.agents.skill import SkillAgent
from app.memory.base import BaseMemoryStore
from app.api.schemas import SkillDTO
from app.config import settings
from app.deps import get_default_llm


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

    print(f"\n[Skill Prompt Content]:\n{human_msg.content}")

    # Assertions
    assert human_msg is not None
    assert "Make a Coffee" in human_msg.content
    assert "Coffee_Machine_01" in human_msg.content
    assert "GENERIC Standard Operating Procedure" in human_msg.content


@pytest.mark.asyncio
async def test_skill_retrieval_success(mock_dependencies):
    """
    Verifies that if memory returns a skill, the agent formats it correctly for the prompt.
    """
    mock_llm, mock_memory = mock_dependencies
    
    # 1. Setup Mock Memory to return a hit
    fake_skill = SkillDTO(
        task_name="Make Toast",
        description="Toast bread in toaster.",
        steps_text="1. Put bread in toaster.\n2. Push lever down.",
        embedding=[]
    )
    mock_memory.fetch_similar_skills = AsyncMock(return_value=[fake_skill])
    
    agent = SkillAgent(llm=mock_llm, memory_store=mock_memory)

    # 2. Run Retrieve
    result = await agent.retrieve_skill("Make Toast")
    
    print(f"\n[Retrieved Skill String]:\n{result}")

    # 3. Assertions
    assert "--- KNOWN RECIPE / SKILL ---" in result
    assert "Make Toast" in result
    assert "Put bread in toaster" in result


# This ensures that even if we Mock the DB, the Retrieval formatting logic works as expected.
# not yet use the docker db
@pytest.mark.paid
@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_skill_retrieval_live_scenario(mock_dependencies):
    """
    Scenario: The agent asks "How to Make Toast". 
    We pretend the DB found a match.
    Expected: The agent returns a correctly formatted string ready for the prompt context.
    """
    _, mock_memory = mock_dependencies # Mock memory
    real_llm = get_default_llm()       # Real LLM (not used for retrieval, but good for consistency)
    
    # 1. Pre-load the Mock Memory with a "Found" skill
    found_skill = SkillDTO(
        task_name="Make Toast",
        description="A simple guide to making toast.",
        steps_text="1. Put bread in toaster.\n2. Wait.",
        embedding=[] 
    )
    mock_memory.fetch_similar_skills = AsyncMock(return_value=[found_skill])
    
    agent = SkillAgent(llm=real_llm, memory_store=mock_memory)

    # 2. Execute Retrieval
    # (In a real scenario, this involves embedding the query, but here we just test the formatting logic)
    retrieved_text = await agent.retrieve_skill("Make Toast")
    
    print(f"\n[Live Retrieval Output]:\n{retrieved_text}")

    # 3. Assertions
    assert "--- KNOWN RECIPE / SKILL ---" in retrieved_text
    assert "Make Toast" in retrieved_text
    # Verify it handles the content correctly
    assert "1. Put bread in toaster." in retrieved_text
    

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_skill_learning_live_scenario(mock_dependencies):
    """
    Scenario: Agent completed 'Cook Burger'. We pass raw actions and expect a generalized SOP.
    Expected: LLM returns a valid SkillDTO, and agent saves it to memory.
    """
    _, mock_memory = mock_dependencies # Use Real LLM, but Mock Memory
    real_llm = get_default_llm()
    
    agent = SkillAgent(llm=real_llm, memory_store=mock_memory)

    # Input: Raw, messy actions
    task_name = "Cook Steamed Fish"
    raw_history = [
        {"action": "Move", "coord": {"x": 12.5, "y": 0, "z": 5}},
        {"action": "Interact", "target": "Fridge_02"},
        {"action": "Grab", "item": "Raw_Fish_ID_99"},
        {"action": "Move", "coord": {"x": 14.0, "y": 0, "z": 5}},
        {"action": "Interact", "target": "Steamer_Pot_01"},
        {"action": "Wait", "seconds": 10},
        {"action": "Grab", "item": "Cooked_Fish"}
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
    
    print(f"\n[Generated Skill]:\n{saved_skill}")

    assert isinstance(saved_skill, SkillDTO)
    assert saved_skill.task_name == "Cook Steamed Fish"
    
    # Check if LLM generalized the instructions
    assert "12.5" not in saved_skill.steps_text, "LLM failed to remove raw coordinates!"
    assert "Fridge" in saved_skill.steps_text, "LLM missed key object 'Fridge'"