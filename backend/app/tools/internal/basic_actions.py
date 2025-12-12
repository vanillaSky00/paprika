from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.tools.base import BaseToolBuilder, tool_registry
from app.tools.context import ToolContext


class MoveInput(BaseModel):
    location_id: str = Field(
        description="The ID of the location or object to move to (e.g., 'Kitchen', 'Stove_01')."
    )


class InteractInput(BaseModel):
    target_id: str = Field(description="The ID of the object to interact with.")
    interaction_type: str = Field(
        description="Type of interaction: 'use', 'pick_up', 'open', 'close'.",
        default="use",
    )


class SayInput(BaseModel):
    text: str = Field(description="The sentence to speak out loud.")


class ThinkInput(BaseModel):
    thought: str = Field(
        description="The content of your internal monologue. No one else hears this."
    )


@tool_registry.register
class MoveToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def move_logic(location_id: str):
            # Sends a command to Unity
            return {"status": "moving", "target": location_id}

        return StructuredTool.from_function(
            func=move_logic,
            name="move_to",
            description="Walk to a specific location or object.",
            args_schema=MoveInput,
        )


@tool_registry.register
class InteractToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def interact_logic(target_id: str, interaction_type: str = "use"):
            return {
                "status": "interacting",
                "target": target_id,
                "type": interaction_type,
            }

        return StructuredTool.from_function(
            func=interact_logic,
            name="interact",
            description="Interact with a nearby object (open, pick up, use).",
            args_schema=InteractInput,
        )


@tool_registry.register
class SayToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def say_logic(text: str):
            return {"status": "speaking", "content": text}

        return StructuredTool.from_function(
            func=say_logic,
            name="say",
            description="Speak to nearby players or NPCs.",
            args_schema=SayInput,
        )


@tool_registry.register
class ThinkToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def think_logic(thought: str):
            # Unity will receive this and can show a 💭 bubble above the head
            return {"status": "thinking", "content": thought}

        return StructuredTool.from_function(
            func=think_logic,
            name="think",
            description="Log a private thought. Use this to plan, reflect, or observe silently.",
            args_schema=ThinkInput,
        )
