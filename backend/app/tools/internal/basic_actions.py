from langchain_core.tools import StructuredTool
from app.tools.base import BaseToolBuilder, tool_registry
from app.tools.context import ToolContext
# IMPORT YOUR NEW SCHEMAS
from app.tools.schemas import MoveInput, PickupInput, PutDownInput

@tool_registry.register
class MoveToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        # NOTICE: Argument name changed to 'id' to match schema!
        def move_logic(id: str):
            return {"status": "moving", "target": id}

        return StructuredTool.from_function(
            func=move_logic,
            name="move_to",
            description="Walk to a specific location or object.",
            args_schema=MoveInput, # <--- Uses the strictly defined schema
        )

@tool_registry.register
class PickupToolBuilder(BaseToolBuilder):
    def build(self, context: ToolContext) -> StructuredTool:
        def pickup_logic(id: str):
            return {"status": "picking_up", "target": id}

        return StructuredTool.from_function(
            func=pickup_logic,
            name="pickup",
            description="Pick up an item.",
            args_schema=PickupInput,
        )
        
@tool_registry.register
class PutDownToolBuilder(BaseToolBuilder): 
    def build(self, context: ToolContext) -> StructuredTool:
        def put_down_logic(id: str):
            return {"status": "placed", "target": id}

        return StructuredTool.from_function(
            func=put_down_logic, # Use the new logic function
            name="put_down",
            description="Put down an item.",
            args_schema=PutDownInput, # Ensure this matches schemas.py
        )

# ... (Repeat for Say, Think)