import pytest
from unittest.mock import MagicMock
from app.llm.base import BaseLLMClient
from app.agents.critic import CriticAgent
from app.config import settings
from app.deps import get_default_llm
from app.api.schemas import CriticOutput, TraceStep

# Define skip logic
should_skip_live = (
    not settings.OPENAI_API_KEY or 
    str(settings.OPENAI_API_KEY).startswith("dummy")
)

def test_critic_prompt_rendering(dummy_perception):
    mock_llm = MagicMock(spec=BaseLLMClient)
    agent = CriticAgent(llm=mock_llm, mode="auto")

    task = "Cook a fancy burger"
    human_msg = agent.render_human_message(
        perception=dummy_perception, 
        current_task=task
    )

    print(f"\n[Critic Prompt]:\n{human_msg.content}")

    assert human_msg is not None
    assert task in human_msg.content
    assert "Kitchen_A" in human_msg.content

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    should_skip_live,
    reason="OPENAI_API_KEY missing or dummy; skipping live test.",
)
async def test_critic_integration_live_failure_scenario(dummy_perception):
    llm = get_default_llm()
    agent = CriticAgent(llm, mode="auto")

    # Use nested 'self.held_item'
    dummy_perception.self.held_item = None
    
    result = await agent.check_task_success(
        perception=dummy_perception, 
        current_task="Cook a burger",
        max_retries=3
    )

    print(f"\n[Critic Failure Test] Verdict: {result}")
    assert isinstance(result, CriticOutput)
    assert result.success is False

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    should_skip_live,
    reason="OPENAI_API_KEY missing or dummy; skipping live test.",
)
async def test_critic_integration_live_success_scenario(dummy_perception):
    llm = get_default_llm()
    agent = CriticAgent(llm, mode="auto")

    # Use nested 'self.held_item'
    dummy_perception.self.held_item = {"id": "Tomato"}
    
    # Add a success trace step
    dummy_perception.execution_trace = [
        TraceStep(step_index=1, function="pickup", target_id="Tomato", status="success", message="Picked up Tomato")
    ]
    
    result = await agent.check_task_success(
        perception=dummy_perception, 
        current_task="Hold a Tomato",
        max_retries=3
    )

    print(f"\n[Critic Success Test] Verdict: {result}")
    assert isinstance(result, CriticOutput)
    assert result.success is True