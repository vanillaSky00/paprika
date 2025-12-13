import pytest
from app.agents.action import ActionAgent
from app.config import settings
from app.deps import get_default_llm
from app.tools import load_global_tools

@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
def test_action_integration_prompt_rendering(dummy_perception):
    llm = get_default_llm()
    tools = load_global_tools(settings=settings)
    agent = ActionAgent(llm, tools)

    print("TOOLS LEN =", len(tools))
    print("TOOLS =", [getattr(t, "name", type(t).__name__) for t in tools])

    system_msg = agent.render_system_message()
    human_msg = agent.render_human_message(
        perception=dummy_perception, current_task="demo"
    )

    print(system_msg)
    print(human_msg)

    # Assert directly on message content (better than captured output)
    assert system_msg is not None
    assert human_msg is not None
    assert "Kitchen_A" in human_msg.content
    assert "Stove_01" in human_msg.content


# Marks this test as async (requires pytest-asyncio installed)
@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
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
        critique=None,
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
    assert first_action.function in ["move_to", "say", "interact"], (
        f"Unexpected tool used: {first_action.function}"
    )
