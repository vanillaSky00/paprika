import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.tools.base import tool_registry, BaseToolBuilder
from app.tools.context import ToolContext

class WeatherInput(BaseModel):
    city: str = Field(description="The name of the city (e.g., 'Tokyo', 'New York')")
    
@tool_registry.register
class WeatherToolBuilder(BaseToolBuilder):
    
    def build(self, context: ToolContext) -> StructuredTool | None:
        
        api_key = getattr(context.settings, "OPENWEATHER_API_KEY", None)
        base_url = getattr(context.settings, "OPENWEATHER_BASE_URL", None)
        
        if not (api_key and base_url):
            return None
        
        async def get_weather(city: str) -> str:
            pass
        
        return StructuredTool.from_function(
            func=get_weather,
            name="get_current_weather",
            description="Get the current weather conditions for a specific city.",
            args_schema=WeatherInput
        )