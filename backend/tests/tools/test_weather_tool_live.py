import pytest
from app.tools.context import ToolContext
from app.tools.external.weather import WeatherToolBuilder
from app.config import settings

# --- Integration Check (Real API Call) ---
@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.skipif(
    not settings.OPENWEATHER_API_KEY,
    reason="Skipping integration test: OPENWEATHER_API_KEY not found in env.",
)
@pytest.mark.integration
async def test_weather_tool_real_call():
    """
    This test actually hits the internet. 
    It will SKIP if you don't have an API key in your environment.
    """
    ctx = ToolContext(settings=settings)

    builder = WeatherToolBuilder()
    tool = builder.build(ctx)
    
    assert tool is not None, "Tool should successfully build with a valid key"
    assert tool.name == "get_current_weather"
    
    # 4. EXECUTE the tool (Async)
    # We manually invoke the 'coroutine' to simulate LangGraph calling it
    result = await tool.coroutine(city="Tokyo")

    # 5. Verify Response
    print(f"\nAPI Response: {result}") # Visible if you run pytest -s
    
    # It should look like "The weather in Tokyo is clouds, 15.5°C."
    # We check for success indicators rather than exact string
    assert "Error" not in result
    assert "weather in" in result