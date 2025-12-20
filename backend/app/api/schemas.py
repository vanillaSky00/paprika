from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --- 1. ENUMS ---
# (Kept simple, mainly for high-level state)


class GameMode(str, Enum):
    REALITY = "reality"
    DREAM = "dream"


# --- 2. PERCEPTION (INPUT FROM UNITY) ---


class WorldObject(BaseModel):
    """
    Represents a physical thing the agent sees.
    Used for 'nearby_objects' in Perception.
    """

    id: str  # Unique ID from Unity (e.g., "Stove_01", "Tomato_Clone(5)")
    type: str  # "Station", "Ingredient", "Prop"
    position: dict[str, float]  # {"x": 1.0, "y": 0.0, "z": 5.0}
    distance: float  # Distance from agent
    state: str | None = "default"  # "on", "off", "open", "empty", "burnt"


class Perception(BaseModel):
    """
    INPUT: What Unity sends every tick.
    Now supports the 'Voyager' feedback loop and 'Visuals'.
    """

    # Context
    time_hour: int
    day: int
    mode: GameMode
    location_id: str
    player_nearby: bool = False

    # Visuals (The "Voxel" equivalent for Unity)
    # The agent needs to know there is a 'Stove' nearby to decide to cook.
    nearby_objects: list[WorldObject] = []

    # Body State (Crucial for Cooking/Crafting)
    held_item: str | None = None  # e.g., "Tomato" or None

    # The "Critic" Feedback Loop
    # Unity tells us if the LAST plan worked.
    # e.g., "Success" or "Failed: Stove is too far away"
    last_action_status: str | None = None
    last_action_error: str | None = None


# --- 3. MEMORY (INTERNAL) ---


class MemoryDTO(BaseModel):
    id: int
    in_game_day: int
    time_slot: int
    mode: str
    location_id: str
    content: str
    memory_type: str
    emotion_tags: list[str] = []
    importance: float
    created_at: datetime
    embedding: list[float] | None = None
    model_config = ConfigDict(from_attributes=True)


class CreateMemoryDTO(BaseModel):
    day: int
    time: int
    mode: str
    location_id: str
    content: str
    memory_type: str
    emotion_tags: list[str] = []
    importance: float = 0.5

class SkillDTO(BaseModel):
    task_name: str
    description: str
    steps_text: str
    embedding: list[float] | None=None

# --- 4. ACTION (OUTPUT TO UNITY) ---


class AgentAction(BaseModel):
    """
    OUTPUT: A dynamic 'Function Call' for Unity to execute.
    Instead of rigid enums, we use a generic 'tool_name' and 'args'.
    This matches the JSON output from your ActionAgent.
    """

    # The thought process (for debugging/UI bubbles)
    thought_trace: str | None = None

    # The Command
    function: str  # e.g., "move_to", "interact", "say", "spawn_object"
    args: dict[str, Any] = Field(
        default_factory=dict
    )  # e.g., {"target_id": "Stove_01"} or {"text": "Hi!"}

    # Meta-data for the Agent (Did this finish the goal?)
    plan_complete: bool = False


class CriticOutput(BaseModel):
    success: bool = Field(description="Did the agent complete the ULTIMATE GOAL? (True/False)")
    reasoning: str = Field(description="Explanation of why it succeeded or failed.")
    feedback: str = Field(description="Constructive advice for the next step. If failed, say exactly what to fix.")
    

class CurriculumOutput(BaseModel):
    task: str = Field(description="The concise task name, e.g., 'Cook the raw meat'.")
    reasoning: str = Field(description="Why this task is the logical next step.")
    difficulty: int = Field(description="Estimated difficulty (1-10).")
    
