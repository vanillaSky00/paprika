import os
import pytest
from pydantic import BaseModel

from app.llm.openai_client import OpenAIClient
from app.config import settings

class FakeAction(BaseModel):
    action: str
    reason: str
    
@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
@pytest.mark.integration
async def test_openai_client_structure_live():
    """
    Live integration test for OpenAIClient.generate_structured().
    This will call the real OpenAI API and cost money.
    Run manually when you want to verify the end-to-end behavior.
    """
    
    client = OpenAIClient(api_key=settings.OPENAI_API_KEY)
    
    result = await client.generate_structured(
        system_prompt="You are a test game agent. Respond with a short JSON-like action.",
        user_message="The player says: 'Jump over the gap.",
        response_model=FakeAction
    )
    
    assert isinstance(result, FakeAction)
    assert isinstance(result.action, str)
    assert isinstance(result.reason, str)
    assert result.action != ""
    assert result.reason != ""
    
    assert "jump" in result.action.lower() or "jump" in result.reason.lower()
    