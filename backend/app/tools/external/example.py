import requests
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from app.tools.base import tool_registry, BaseToolBuilder
from app.tools.context import ToolContext

class ExampleInput(BaseModel):
    input1: str = Field(description="The name of the city (e.g., 'Tokyo', 'New York')")

class ExampleToolBuilder(BaseToolBuilder):
    
    def build(self, context: ToolContext) -> StructuredTool | None:
        
        api_key = getattr(context.settings, "EXAMPLE_API_KEY", None)
        base_url = getattr(context.settings, "EXAMPLE_API_URL", None)
        
        if not (api_key and base_url):
            return None

        def get_example(city: str) -> str:
            try:
                pass
            except Exception:
                pass

        return StructuredTool.from_function(
            func=get_example,
            name="get_current_example",
            description="Get the current example conditions for a specific event.",
            args_schema=ExampleInput
        )