import pytest
from unittest.mock import MagicMock
from app.llm.base import BaseLLMClient
from app.agents.action import ActionAgent
from app.context.view import build_perception_context
from app.core.config import settings
from app.core.deps import get_default_llm
from app.tools import load_global_tools

should_skip_live = (
    not settings.OPENAI_API_KEY or
    str(settings.OPENAI_API_KEY).startswith("dummy")
)


def test_action_integration_prompt_rendering(dummy_perception):
    mock_llm = MagicMock(spec=BaseLLMClient)
    tools = load_global_tools(settings=settings)
    agent = ActionAgent(llm=mock_llm, tools=tools)

    context = build_perception_context(dummy_perception)
    system_msg = agent.render_system_message()
    human_msg = agent.render_human_message(
        context=context,
        current_task="demo",
    )

    assert system_msg is not None
    assert human_msg is not None
    assert "demo" in human_msg.content
    assert "Stove_01" in human_msg.content
    assert "FAILED" in human_msg.content


@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    should_skip_live,
    reason="OPENAI_API_KEY missing or dummy; skipping live test.",
)
async def test_action_integration_live(dummy_perception):
    """
    LIVE INTEGRATION TEST
    """
    llm = get_default_llm()
    tools = load_global_tools(settings=settings)
    agent = ActionAgent(llm=llm, tools=tools)

    assert len(tools) > 0, "No tools were loaded from the registry!"

    current_task = "Cook a burger"
    context = build_perception_context(dummy_perception, current_task=current_task)
    actions = await agent.generate_plan(
        context=context,
        current_task=current_task,
        last_plan="",
        critique="",
    )

    assert isinstance(actions, list)
    assert len(actions) > 0

    first_action = actions[0]
    assert hasattr(first_action, "function")
    assert hasattr(first_action, "args")

    print(f"\nGenerated Plan: {[a.function for a in actions]}")
    assert first_action.function in ["move_to", "say", "interact", "pickup"]
