import logging

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.base import BaseToolBuilder, tool_registry
from app.tools.context import ToolContext

logger = logging.getLogger(__name__)


class WeatherInput(BaseModel):
    city: str = Field(description="The name of the city (e.g., 'Tokyo', 'New York')")


@tool_registry.register
class WeatherToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool | None:
        api_key = getattr(context.settings, "OPENWEATHER_API_KEY", None)
        base_url = getattr(context.settings, "OPENWEATHER_BASE_URL", None)

        if not (api_key and base_url):
            return None

        # Check https://openweathermap.org/current#name
        async def get_weather(city: str) -> str:
            url = f"{base_url}/data/2.5/weather"
            params = {"q": city, "appid": api_key, "units": "metric"}
            # connect=5.0: Max time to establish connection
            # read=5.0: Max time to wait for data after connecting
            timeout = httpx.Timeout(5.0, connect=5.0, read=5.0)

            print(url)
            print(params)
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    resp = await client.get(url=url, params=params)
                    resp.raise_for_status()

                    data = resp.json()
                    desc = data["weather"][0]["description"]
                    temp = data["main"]["temp"]
                    return f"The weather in {city} is {desc}, {temp}°C."

                except httpx.TimeoutException:
                    logger.warning(f"Weather API timed out for {city}")
                    return "Error: Weather service is too slow. Try again later."

                except Exception as e:
                    logger.error(f"Weather API failed: {e}")
                    return f"Error fetching weather: {e}"

        return StructuredTool.from_function(
            func=None,  # Sync version
            coroutine=get_weather,  # Async version
            name="get_current_weather",
            description="Get the current weather conditions for a specific city.",
            args_schema=WeatherInput,
        )
