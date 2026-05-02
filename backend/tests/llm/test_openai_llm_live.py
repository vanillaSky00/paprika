import pytest
from pydantic import BaseModel

from app.core.config import settings
from app.llm.openai_client import OpenAIClient

class FakeAction(BaseModel):
    action: str
    reason: str

# Define skip logic
should_skip_live = (
    not settings.OPENAI_API_KEY or 
    str(settings.OPENAI_API_KEY).startswith("dummy")
)

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    should_skip_live,
    reason="OPENAI_API_KEY missing or dummy; skipping live test.",
)
@pytest.mark.integration
async def test_openai_client_structure_live():
    """
    Live integration test for OpenAIClient.generate_structured().
    """
    client = OpenAIClient(api_key=settings.OPENAI_API_KEY)

    result = await client.generate_structured(
        system_prompt="You are a test game agent. Respond with a short JSON-like action.",
        user_message="The player says: 'Jump over the gap.",
        response_model=FakeAction,
    )

    assert isinstance(result, FakeAction)
    assert isinstance(result.action, str)
    assert isinstance(result.reason, str)
    assert result.action != ""