from app.tools import ToolContext

def test_weather_tool_disabled_without_key(settings_stub):
    ctx = ToolContext(settings=settings_stub)
    builder = WeatherToolBuilder()
    tool = builder.build(ctx)
    assert tool is None
