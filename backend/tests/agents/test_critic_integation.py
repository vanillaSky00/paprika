import pytest
from unittest.mock import MagicMock
from app.llm.base import BaseLLMClient
from app.agents.critic import CriticAgent
from app.config import settings
from app.deps import get_default_llm
from app.api.schemas import CriticOutput


def test_critic_prompt_rendering(dummy_perception):
    """
    Verifies that the Critic correctly formats the Observation into a text prompt.
    """
    mock_llm = MagicMock(spec=BaseLLMClient)
    # Critic doesn't need tools
    agent = CriticAgent(llm=mock_llm, mode="auto")

    # 1. Render the Prompt
    task = "Cook a fancy burger"
    human_msg = agent.render_human_message(
        perception=dummy_perception, 
        current_task=task
    )

    print(f"\n[Critic Prompt]:\n{human_msg.content}")

    # 2. Assertions
    assert human_msg is not None
    # Check Goal is present
    assert task in human_msg.content
    # Check Context is present
    assert "Kitchen_A" in human_msg.content
    assert "Stove_01" in human_msg.content
    # Check Section headers are present
    assert "--- GOAL ---" in human_msg.content
    assert "--- CURRENT STATE ---" in human_msg.content


@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_critic_integration_live_failure_scenario(dummy_perception):
    """
    Scenario: Agent attempts to 'Cook a burger' but is holding NOTHING.
    Expected: Critic should return success=False.
    """
    llm = get_default_llm()
    agent = CriticAgent(llm, mode="auto")

    # Override perception to ensure failure state
    dummy_perception.held_item = None
    
    # Run Critic
    result = await agent.check_task_success(
        perception=dummy_perception, 
        current_task="Cook a burger",
        max_retries=3
    )

    print(f"\n[Critic Failure Test] Verdict: {result}")

    # Assertions
    assert isinstance(result, CriticOutput)
    assert result.success is False, "Critic incorrectly marked task as success!"
    assert len(result.feedback) > 5, "Critic failed to provide feedback."


@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_critic_integration_live_success_scenario(dummy_perception):
        """
        Scenario: Agent wants to 'Hold a Tomato' and is holding 'Tomato'.
        Expected: Critic should return success=True.
        """
        llm = get_default_llm()
        agent = CriticAgent(llm, mode="auto")
    
        dummy_perception.held_item = "Tomato"
        dummy_perception.last_action_status = "Success"      
        dummy_perception.last_action_error = None            
        
        # Run Critic
        result = await agent.check_task_success(
            perception=dummy_perception, 
            current_task="Hold a Tomato",
            max_retries=3
        )
    
        print(f"\n[Critic Success Test] Verdict: {result}")
    
        # Assertions
        assert isinstance(result, CriticOutput)
        assert result.success is True, f"Critic failed! Reasoning: {result.reasoning}"