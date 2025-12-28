from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

# --- ENUMS ------------------------------------------------
class GameMode(str, Enum):
    REALITY = "reality"
    DREAM = "dream"


# --- PERCEPTION (INPUT FROM UNITY) ------------------------
class TraceStep(BaseModel):
    step_index: int
    function: str
    target_id: str = ""
    status: str
    message: str = ""

class ObjectView(BaseModel):
    id: str
    type: str = "Unknown"
    distance: float = 0.0
    state: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    def status_summary(self) -> str:
        if not self.state:
            return "(default)"
            
        flags = []
        
        for k, v in self.state.items():
            # 🛑 1. Skip keys you never want to show (Noise reduction)
            if k in ['is_empty', 'id', 'type', 'distance']: 
                continue
                
            # ✅ 2. Handle Booleans (e.g., is_on: true -> "is_on")
            if isinstance(v, bool):
                if v is True:
                    flags.append(k)
            
            # ✅ 3. Handle Strings & Numbers (e.g., held_item: "Meat" -> "held_item:Meat")
            # This is the part you were missing!
            elif isinstance(v, (str, int, float)) and v:
                flags.append(f"{k}:{v}")

        # 4. Legacy "contains_items" fallback (optional, keeps your old logic working)
        # If we didn't find a specific item string, but it's not empty, say generic "contains_items"
        has_explicit_item = any(isinstance(v, str) for v in self.state.values())
        if self.state.get("is_empty") is False and not has_explicit_item:
            flags.append("contains_items")
            
        return f"({','.join(flags)})" if flags else ""

class Sensory(BaseModel):
    player_nearby: bool = False
    visible_objects: list[ObjectView] = Field(default_factory=list)
    reachable_objects: list[ObjectView] = Field(default_factory=list)

class SelfState(BaseModel):
    time_hour: int
    current_zone: str
    held_item: dict[str, Any] | None | str = "Nothing" # handle if unity give null and need nothing for better prompts

class Statistics(BaseModel):
    table_item_count: int = 0
    table_items: list[str] = Field(default_factory=list)
    
class Perception(BaseModel):
    """
    Why: Unity send character's scenory perception for agent to make plans
    """
    model_config = ConfigDict(extra="ignore") # Ignores extra fields from Unity, preventing crashes on updates
    
    self: SelfState
    sensory: Sensory
    execution_trace: list[TraceStep] = Field(default_factory=list)
    statistics: Statistics 


# --- DB data or Memory ------------------------------------
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


# --- Agent Output  ---------------------------------------------------
# Only AgentAction Output TO UNITY)

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

class CriticOutput(BaseModel):
    success: bool = Field(description="Did the agent complete the ULTIMATE GOAL? (True/False)")
    reasoning: str = Field(description="Explanation of why it succeeded or failed.")
    feedback: str = Field(description="Constructive advice for the next step. If failed, say exactly what to fix.")
    
class CurriculumOutput(BaseModel):
    task: str = Field(description="The concise task name, e.g., 'Cook the raw meat'.")
    reasoning: str = Field(description="Why this task is the logical next step.")
    difficulty: int = Field(description="Estimated difficulty (1-10).")