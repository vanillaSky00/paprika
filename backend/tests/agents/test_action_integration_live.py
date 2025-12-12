import pytest
from app.agents.action import ActionAgent
from app.tools import load_global_tools
from app.deps import get_default_llm
from app.config import settings

# Marks this test as async (requires pytest-asyncio installed)
@pytest.mark.paid
@pytest.mark.asyncio
async def test_action_integration_live(dummy_perception):
    """
    LIVE INTEGRATION TEST
    ---------------------
    1. Loads real Tools.
    2. connects to real LLM (OpenAI/Ollama).
    3. Sends a fake Unity Perception.
    4. Verifies the LLM returns a valid plan.
    """
    
    llm = get_default_llm()  
    tools = load_global_tools(settings=settings)
    agent = ActionAgent(llm=llm, tools=tools)

    assert len(tools) > 0, "No tools were loaded from the registry!"

    current_task = "Cook a burger"
    actions = await agent.generate_plan(
        perception=dummy_perception,
        current_task=current_task,
        last_plan=None,
        critique=None
    )

    # 4. Assertions
    # Check that we got a list back
    assert isinstance(actions, list), "Agent returned something that is not a list"
    
    # Check that the list is not empty (LLM should generate at least one step)
    assert len(actions) > 0, "LLM failed to generate any actions"

    # Check the first action structure
    first_action = actions[0]
    
    # Verify Pydantic Schema
    assert hasattr(first_action, "function"), "Action missing 'function' field"
    assert hasattr(first_action, "args"), "Action missing 'args' field"
    
    # Verify Logic (Soft check)
    # Usually the first step for cooking is moving to the fridge or stove
    print(f"\nGeneratd Plan: {[a.function for a in actions]}")
    assert first_action.function in ["move_to", "say", "interact"], f"Unexpected tool used: {first_action.function}"