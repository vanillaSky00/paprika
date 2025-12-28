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
        """
        Auto-generates the string like '(is_on,progress:50%)' 
        directly from the dictionary.
        """
        if not self.state:
            return "(default)"
            
        flags = []
        
        # 1. Booleans (is_on=True) - Explicitly IGNORE 'is_empty'
        flags.extend([k for k, v in self.state.items() 
                      if v is True and k != 'is_empty'])
        
        # 2. Progress Numbers
        if "cooking_progress" in self.state:
            val = self.state["cooking_progress"]
            if val > 0:
                flags.append(f"progress:{int(val)}%")
                
        # 3. Container Logic (is_empty=False -> "contains_items")
        if self.state.get("is_empty") is False:
            flags.append("contains_items")
            
        return f"({','.join(flags)})" if flags else ""

class Sensory(BaseModel):
    player_nearby: bool = False
    visible_objects: list[ObjectView] = Field(default_factory=list)

class SelfState(BaseModel):
    time_hour: int
    current_zone: str
    held_item: dict[str, Any] | None = None # Simple dict is fine if structure varies

class Perception(BaseModel):
    """
    Why: Unity send character's scenory perception for agent to make plans
    """
    model_config = ConfigDict(extra="ignore") # Ignores extra fields from Unity, preventing crashes on updates
    
    self: SelfState
    sensory: Sensory
    execution_trace: list[TraceStep] = Field(default_factory=list)


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