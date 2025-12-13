from unittest.mock import MagicMock

from app.tools.context import ToolContext
from app.tools.external.weather import WeatherToolBuilder


def test_weather_tool_disabled_without_key():
    # 1. Setup a fake settings object with NO key
    settings_stub = MagicMock()
    # Ensure getting the attribute returns None or empty string
    settings_stub.OPENWEATHER_API_KEY = None

    ctx = ToolContext(settings=settings_stub)
    builder = WeatherToolBuilder()

    # 2. Build
    tool = builder.build(ctx)

    # 3. Assert
    assert tool is None, "Tool should be None when API key is missing"
