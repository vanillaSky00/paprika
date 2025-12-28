from pydantic import BaseModel, Field

# --- STANDARD INPUT SCHEMAS ---
# We use 'id' universally to prevent LLM confusion.

class MoveInput(BaseModel):
    id: str = Field(
        ..., 
        description="The unique ID of the location or object to move to (e.g., 'CheeseBox', 'TomatoBox')."
    )

class PickupInput(BaseModel):
    id: str = Field(
        ..., 
        description="The unique ID of the item to pick up (e.g., 'CheeseBox', 'LettuceBox'). "
    )

class PutDownInput(BaseModel):
    id: str = Field(
        ..., 
        description="The unique ID of the surface to place the item on (e.g., 'LettuceBox', 'TomatoBox')."
    )

# class InteractInput(BaseModel):
#     id: str = Field(..., description="The ID of the object to interact with.")
#     interaction_type: str = Field(
#         default="use",
#         description="Type of interaction: 'use', 'open', 'close'."
#     )

# class SayInput(BaseModel):
#     text: str = Field(..., description="The sentence to speak out loud.")

# class ThinkInput(BaseModel):
#     thought: str = Field(..., description="The content of your internal monologue.")